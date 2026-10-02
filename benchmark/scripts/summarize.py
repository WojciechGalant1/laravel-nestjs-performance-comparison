#!/usr/bin/env python3
"""Summarise the runs written by scripts/run-scenario.sh.

Usage:
  python3 scripts/summarize.py <scenario>              e.g. ... s1
  python3 scripts/summarize.py --freeze-h3-threshold   after S1, before S3

Writes results/<scenario>/runs.csv (one row per repetition and endpoint label) and
results/<scenario>/summary.csv (median and standard deviation across repetitions).
S1 prints the H1 table (low-load set, bootstrap CI of |Δp95|). S2 prints the H2
table (p95 slope below saturation). S3 prints the H3 table (signed D_k, bootstrap
CI, threshold Y from results/h3_threshold.json). Secondary Little's-law and CPU
per request figures are printed for every scenario and do not decide a verdict.

Definitions (Sections 3.3, 3.5 and 3.6 of the methodology):
- The ramp-up is excluded: the steady-state window starts rampup_s after the first
  measured sample and ends with the last completed sample.
- Percentiles use the nearest-rank method over all samples of a label in the window.
- Throughput counts successful samples only; the error rate counts every failed
  sample (assertion failures, HTTP errors and timeouts).
- CPU is reported as docker stats reports it (100% = one CPU) and as a share of the
  CPUs allocated to the application container. The same stream covers nginx,
  postgres and the JMeter container.
- Delta between frameworks is relative to the mean of the two values, so neither
  framework is the reference: |a - b| / ((a + b) / 2).
- A concurrency level belongs to a low-load set when, for both frameworks and
  every endpoint that set requires, (a) X(N)/(N·X(1)) >= 0.80, (b) application
  CPU is below 80% of its container limit, and (c) PostgreSQL CPU is below 80%
  of its container limit. The set is the longest prefix of {1, 2, 4, 10} that
  passes. H1 uses one set over EP1, EP2 and EP8. H3 uses one set per pair
  (EP1, EP_k).
- Two secondary figures are printed beside the verdict and do not enter it.
  Little's law mean is concurrency divided by throughput (N/RPS). CPU time per
  request is the application container's CPU, as a fraction of one core, divided
  by throughput.
"""

import csv
import json
import math
import random
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "results"
SETUP_LABELS = {"SETUP_login"}
H1_LIMIT_PCT = 15.0
H1_ERROR_LIMIT_PCT = 1.0
H1_ENDPOINTS = ("EP1", "EP2", "EP8")
H3_ENDPOINTS = ("EP4", "EP5", "EP6")
H3_REQUIRED = ("EP4", "EP5")
S3_ENDPOINTS = ("EP1", "EP4", "EP5", "EP6")
H2_SATURATION_PCT = 5.0
H2_SLOPE_MIN_VU = 200
PLANNED_VU = (1, 2, 4, 10)
LOWLOAD_SCALING_MIN = 0.80
LOWLOAD_CPU_SHARE_MAX = 0.80
JMETER_CPU_FLAG_PCT = 80.0
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 20261002
H3_THRESHOLD_PATH = ROOT / "h3_threshold.json"
H3_Y_FLOOR_MS = 2.0
H3_Y_K = 2.0

UNITS = {
    "B": 1 / 1024**2, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024,
    "kB": 1000 / 1024**2, "MB": 1000**2 / 1024**2, "GB": 1000**3 / 1024**2,
}


def to_mib(value):
    for unit in sorted(UNITS, key=len, reverse=True):
        if value.endswith(unit):
            return float(value[: -len(unit)]) * UNITS[unit]
    raise ValueError(f"unknown memory unit: {value}")


def percentile(sorted_values, p):
    rank = max(1, math.ceil(p / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def read_samples(jtl):
    with jtl.open(newline="") as fh:
        return [
            {
                "start": int(row["timeStamp"]),
                "elapsed": int(row["elapsed"]),
                "label": row["label"],
                "success": row["success"] == "true",
            }
            for row in csv.DictReader(fh)
            if row["label"] not in SETUP_LABELS
        ]


def container_role(name):
    for role in ("jmeter", "nginx", "postgres", "app"):
        if f"-{role}-" in name or name.endswith(role) or name.endswith(f"-{role}"):
            return role
    return name


def container_stats(stats_csv, window_wsl, cpus, postgres_cpus=None):
    """Mean and peak per container over the load window (WSL clock)."""
    lo, hi = window_wsl
    per = defaultdict(lambda: {"cpu": [], "mem": []})
    with stats_csv.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if lo <= float(row["epoch"]) <= hi:
                per[row["name"]]["cpu"].append(float(row["cpu_perc"]))
                per[row["name"]]["mem"].append(to_mib(row["mem_usage"]))

    out = {}
    for name, values in per.items():
        role = container_role(name)
        if not values["cpu"]:
            continue
        out[f"{role}_cpu_mean"] = statistics.fmean(values["cpu"])
        out[f"{role}_cpu_peak"] = max(values["cpu"])
        out[f"{role}_mem_mean_mib"] = statistics.fmean(values["mem"])
        out[f"{role}_mem_peak_mib"] = max(values["mem"])
    if "app_cpu_mean" in out:
        out["app_cpu_share_pct"] = out["app_cpu_mean"] / (100.0 * cpus)
    pg_cpus = postgres_cpus if postgres_cpus else cpus
    if "postgres_cpu_mean" in out and pg_cpus:
        out["postgres_cpu_share_pct"] = out["postgres_cpu_mean"] / (100.0 * pg_cpus)
    return out


def summarise_run(run_dir):
    meta = json.loads((run_dir / "meta.json").read_text())
    if meta["status"] != "complete":
        return []

    samples = read_samples(run_dir / "results.jtl")
    if not samples:
        return []
    window_start = min(s["start"] for s in samples) + meta["rampup_s"] * 1000
    steady = [s for s in samples if s["start"] >= window_start]
    window_end = max(s["start"] + s["elapsed"] for s in steady)
    window_s = (window_end - window_start) / 1000

    offset = meta["clock_offset_s"]
    stats = container_stats(
        run_dir / "stats.csv",
        (window_start / 1000 - offset, window_end / 1000 - offset),
        meta["app_cpus"],
        meta.get("postgres_cpus") or meta["app_cpus"],
    )

    extra = {}
    if "interleave_seed" in meta:
        extra["interleave_seed"] = meta["interleave_seed"]
    if "framework_order" in meta:
        extra["framework_order"] = meta["framework_order"]
    counts = meta.get("row_counts")
    if isinstance(counts, dict):
        extra["orders_count"] = counts.get("orders")
        extra["order_items_count"] = counts.get("order_items")
        extra["reservations_count"] = counts.get("reservations")

    rows = []
    by_label = defaultdict(list)
    for s in steady:
        by_label[s["label"]].append(s)
    for label, group in sorted(by_label.items()):
        elapsed = sorted(s["elapsed"] for s in group)
        ok = sum(s["success"] for s in group)
        rps = ok / window_s
        row = {
            "scenario": meta["scenario"],
            "mode": meta["mode"],
            "framework": meta["framework"],
            "endpoint": label,
            "users": meta["users"],
            "repetition": meta["repetition"],
            "samples": len(group),
            "window_s": round(window_s, 3),
            "p50_ms": percentile(elapsed, 50),
            "p95_ms": percentile(elapsed, 95),
            "p99_ms": percentile(elapsed, 99),
            "throughput_rps": rps,
            "error_rate_pct": 100 * (len(group) - ok) / len(group),
            **stats,
            **extra,
        }
        if rps > 0:
            row["little_ms"] = meta["users"] / rps * 1000
            if "app_cpu_mean" in stats:
                row["cpu_per_request_ms"] = stats["app_cpu_mean"] / 100 * 1000 / rps
        rows.append(row)
    return rows


def write_csv(path, rows):
    fields = []
    for row in rows:
        fields += [k for k in row if k not in fields]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (f"{v:.3f}" if isinstance(v, float) else v) for k, v in row.items()})


def aggregate(rows):
    keys = ("scenario", "mode", "framework", "endpoint", "users")
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)

    skip = set(keys) | {"repetition", "samples", "window_s", "framework_order",
                       "interleave_seed", "postgres_cpus"}
    summary = []
    for key, group in sorted(groups.items()):
        out = dict(zip(keys, key))
        out["repetitions"] = len(group)
        metrics = [k for k in group[0] if k not in skip and isinstance(group[0].get(k), (int, float))]
        for metric in metrics:
            values = [r[metric] for r in group if isinstance(r.get(metric), (int, float))]
            if not values:
                continue
            out[f"{metric}_median"] = statistics.median(values)
            out[f"{metric}_sd"] = statistics.stdev(values) if len(values) > 1 else 0.0
        summary.append(out)
    return summary


def rel_delta_pct(a, b):
    mean = (a + b) / 2
    return 0.0 if mean == 0 else 100 * abs(a - b) / mean


def ratio(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def fmt_ratio(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/d"
    return f"{value:.2f}x"


def signed_gap(lar_p95, nest_p95):
    return lar_p95 - nest_p95


def d_k(lar_k, nest_k, lar_1, nest_1):
    return signed_gap(lar_k, nest_k) - signed_gap(lar_1, nest_1)


def summary_index(summary):
    return {(r["mode"], r["endpoint"], int(r["users"]), r["framework"]): r for r in summary}


def group_values(rows, mode, endpoint, users, framework, field="p95_ms"):
    return [
        r[field]
        for r in rows
        if r["mode"] == mode
        and r["endpoint"] == endpoint
        and int(r["users"]) == users
        and r["framework"] == framework
        and field in r
    ]


def percentile_ci(samples, lo=2.5, hi=97.5):
    ordered = sorted(samples)
    return percentile(ordered, lo), percentile(ordered, hi)


def bootstrap_rel_delta(lar_vals, nest_vals, rng):
    if not lar_vals or not nest_vals:
        return None
    stats = []
    for _ in range(BOOTSTRAP_N):
        lar = statistics.median(rng.choices(lar_vals, k=len(lar_vals)))
        nest = statistics.median(rng.choices(nest_vals, k=len(nest_vals)))
        stats.append(rel_delta_pct(lar, nest))
    return percentile_ci(stats)


def bootstrap_d_k(rows, mode, endpoint, users, rng):
    groups = {
        "l1": group_values(rows, mode, "EP1", users, "laravel"),
        "n1": group_values(rows, mode, "EP1", users, "nestjs"),
        "lk": group_values(rows, mode, endpoint, users, "laravel"),
        "nk": group_values(rows, mode, endpoint, users, "nestjs"),
    }
    if not all(groups.values()):
        return None
    stats = []
    for _ in range(BOOTSTRAP_N):
        med = {key: statistics.median(rng.choices(vals, k=len(vals))) for key, vals in groups.items()}
        stats.append(d_k(med["lk"], med["nk"], med["l1"], med["n1"]))
    lo, hi = percentile_ci(stats)
    point = d_k(
        statistics.median(groups["lk"]),
        statistics.median(groups["nk"]),
        statistics.median(groups["l1"]),
        statistics.median(groups["n1"]),
    )
    return point, lo, hi


def prefix_of_planned(passing):
    """Longest prefix of the planned VU sequence in which every level passes."""
    members = []
    passing_set = set(passing)
    for vu in PLANNED_VU:
        if vu in passing_set:
            members.append(vu)
        else:
            break
    return members


def lowload_set(summary, endpoints, mode="isolated"):
    """Prefix of planned VU levels that pass scaling, app CPU and Postgres CPU."""
    index = summary_index(summary)
    passing = []
    diagnostics = []
    for vu in PLANNED_VU:
        ok = True
        for endpoint in endpoints:
            for framework in ("laravel", "nestjs"):
                base = index.get((mode, endpoint, 1, framework))
                row = index.get((mode, endpoint, vu, framework))
                if base is None or row is None:
                    ok = False
                    diagnostics.append({
                        "users": vu, "endpoint": endpoint, "framework": framework,
                        "scaling": None, "app_cpu_share": None, "pg_cpu_share": None,
                        "ok": False, "reason": "missing",
                    })
                    continue
                x1 = base["throughput_rps_median"]
                xn = row["throughput_rps_median"]
                scaling = None if x1 == 0 else xn / (vu * x1)
                app_share = row.get("app_cpu_share_pct_median")
                pg_share = row.get("postgres_cpu_share_pct_median")
                pass_scale = scaling is not None and scaling >= LOWLOAD_SCALING_MIN
                pass_app = app_share is not None and app_share < LOWLOAD_CPU_SHARE_MAX
                pass_pg = pg_share is not None and pg_share < LOWLOAD_CPU_SHARE_MAX
                cell_ok = pass_scale and pass_app and pass_pg
                if not cell_ok:
                    ok = False
                diagnostics.append({
                    "users": vu, "endpoint": endpoint, "framework": framework,
                    "scaling": scaling, "app_cpu_share": app_share, "pg_cpu_share": pg_share,
                    "ok": cell_ok,
                })
        if ok:
            passing.append(vu)
    return prefix_of_planned(passing), diagnostics


def print_lowload(members, diagnostics, label):
    print(f"\nLow-load set for {label} (scaling >= {LOWLOAD_SCALING_MIN:g}, "
          f"app and PostgreSQL CPU share < {LOWLOAD_CPU_SHARE_MAX:g} of each "
          f"container limit; prefix of {list(PLANNED_VU)}): "
          f"{members or 'empty'}")
    header = (f"{'endpoint':8} {'VU':>4} {'fw':8} {'X(N)/(N·X(1))':>14} "
              f"{'app CPU':>10} {'PG CPU':>10}  pass")
    print(header)
    print("-" * len(header))
    for row in diagnostics:
        scaling = "n/d" if row["scaling"] is None else f"{row['scaling']:.3f}"
        app = "n/d" if row["app_cpu_share"] is None else f"{100 * row['app_cpu_share']:.1f}%"
        pg = "n/d" if row["pg_cpu_share"] is None else f"{100 * row['pg_cpu_share']:.1f}%"
        print(f"{row['endpoint']:8} {row['users']:>4} {row['framework']:8} {scaling:>14} "
              f"{app:>10} {pg:>10}  {'yes' if row['ok'] else 'no'}")


def pair_levels(members):
    if len(members) >= 2:
        return members[-1], members[-2]
    return None, None


def classify_d_k(lo, hi, y, point_v, point_c):
    if lo is None or hi is None or point_v is None or point_c is None:
        return "not evaluable"
    signs_ok = point_v != 0 and point_c != 0 and (point_v > 0) == (point_c > 0)
    if lo > y and signs_ok:
        return "supported"
    if hi < y:
        return "rejected"
    return "inconclusive"


def flag_jmeter_cpu(summary):
    flagged = [
        r for r in summary
        if r.get("jmeter_cpu_mean_median") is not None
        and r["jmeter_cpu_mean_median"] > JMETER_CPU_FLAG_PCT
    ]
    if not flagged:
        return
    print(f"\nJMeter CPU diagnostic: mean CPU exceeded {JMETER_CPU_FLAG_PCT:g}% of one core "
          "(validity flag, not in any verdict):")
    for r in flagged:
        print(f"  {r['framework']} {r['endpoint']} vu={r['users']} "
              f"jmeter_cpu_mean={r['jmeter_cpu_mean_median']:.1f}%")


def secondary_table(summary):
    """Little's law mean and CPU time per request. Not an input to any verdict."""
    index = summary_index(summary)
    print("\nSecondary, not in the verdict: Little's law mean (N/RPS), application CPU time per request, ratio of median p95")
    print("Container CPU is docker stats percent (100% = one CPU)")
    header = (f"{'mode':9} {'endpoint':8} {'VU':>4} {'Litt L':>8} {'Litt N':>8} {'L/N':>6} "
              f"{'CPU L':>7} {'CPU N':>7} {'L/N':>6} {'p95':>6} "
              f"{'appL':>6} {'appN':>6} {'ngxL':>6} {'ngxN':>6} {'pgL':>6} {'pgN':>6} {'jmL':>6} {'jmN':>6}")
    print(header)
    print("-" * len(header))
    for (mode, endpoint, users, framework), lar in sorted(index.items()):
        if framework != "laravel":
            continue
        nest = index.get((mode, endpoint, users, "nestjs"))
        if nest is None or "little_ms_median" not in lar or "little_ms_median" not in nest:
            continue

        def cell(row, key):
            value = row.get(key)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return None
            return value

        def num(value, digits):
            return "n/d" if value is None else f"{value:.{digits}f}"

        cpu_l, cpu_n = cell(lar, "cpu_per_request_ms_median"), cell(nest, "cpu_per_request_ms_median")
        p95_ratio = ratio(lar["p95_ms_median"], nest["p95_ms_median"])
        print(f"{mode:9} {endpoint:8} {users:>4} {lar['little_ms_median']:>8.2f} {nest['little_ms_median']:>8.2f} "
              f"{fmt_ratio(ratio(lar['little_ms_median'], nest['little_ms_median'])):>6} "
              f"{num(cpu_l, 2):>7} {num(cpu_n, 2):>7} {fmt_ratio(ratio(cpu_l, cpu_n)):>6} "
              f"{fmt_ratio(p95_ratio):>6} "
              f"{num(cell(lar, 'app_cpu_mean_median'), 0):>6} {num(cell(nest, 'app_cpu_mean_median'), 0):>6} "
              f"{num(cell(lar, 'nginx_cpu_mean_median'), 0):>6} {num(cell(nest, 'nginx_cpu_mean_median'), 0):>6} "
              f"{num(cell(lar, 'postgres_cpu_mean_median'), 0):>6} {num(cell(nest, 'postgres_cpu_mean_median'), 0):>6} "
              f"{num(cell(lar, 'jmeter_cpu_mean_median'), 0):>6} {num(cell(nest, 'jmeter_cpu_mean_median'), 0):>6}")


def h1_table(summary, rows):
    members, diagnostics = lowload_set(summary, H1_ENDPOINTS)
    print_lowload(members, diagnostics, "S1")
    print(f"\nH1: 95% bootstrap CI of |Δp95| (10 000 resamples, seed {BOOTSTRAP_SEED}). "
          f"Verdict uses the low-load set only. Threshold {H1_LIMIT_PCT:g}%, error rate < {H1_ERROR_LIMIT_PCT:g}%")
    header = (f"{'mode':9} {'endpoint':8} {'VU':>4} {'p95 L':>8} {'p95 N':>8} {'dp95%':>7} "
              f"{'CI lo':>7} {'CI hi':>7} {'rps L':>9} {'rps N':>9} {'err L%':>7} {'err N%':>7}  tag")
    print(header)
    print("-" * len(header))

    rng = random.Random(BOOTSTRAP_SEED)
    any_reject = False
    all_support = True
    had_verdict_row = False
    index = summary_index(summary)
    for (mode, endpoint, users, framework), lar in sorted(index.items()):
        if framework != "laravel" or endpoint not in H1_ENDPOINTS:
            continue
        nest = index.get((mode, endpoint, users, "nestjs"))
        if nest is None:
            print(f"{mode:9} {endpoint:8} {users:>4}  (no NestJS results yet)")
            continue
        dp95 = rel_delta_pct(lar["p95_ms_median"], nest["p95_ms_median"])
        err_l, err_n = lar["error_rate_pct_median"], nest["error_rate_pct_median"]
        in_set = users in members
        ci = bootstrap_rel_delta(
            group_values(rows, mode, endpoint, users, "laravel"),
            group_values(rows, mode, endpoint, users, "nestjs"),
            rng,
        ) if in_set else None
        lo = hi = None
        if ci:
            lo, hi = ci
        if not in_set:
            tag = "observation"
        else:
            had_verdict_row = True
            if lo is None:
                tag = "n/d"
                all_support = False
            elif max(err_l, err_n) >= H1_ERROR_LIMIT_PCT or lo > H1_LIMIT_PCT:
                tag = "rejected"
                any_reject = True
                all_support = False
            elif hi <= H1_LIMIT_PCT and max(err_l, err_n) < H1_ERROR_LIMIT_PCT:
                tag = "holds"
            else:
                tag = "inconclusive"
                all_support = False
        lo_s = "n/d" if lo is None else f"{lo:.1f}"
        hi_s = "n/d" if hi is None else f"{hi:.1f}"
        print(f"{mode:9} {endpoint:8} {users:>4} {lar['p95_ms_median']:>8.1f} {nest['p95_ms_median']:>8.1f} "
              f"{dp95:>7.1f} {lo_s:>7} {hi_s:>7} {lar['throughput_rps_median']:>9.1f} "
              f"{nest['throughput_rps_median']:>9.1f} {err_l:>7.2f} {err_n:>7.2f}  {tag}")

    if not members:
        verdict = "not evaluable (empty low-load set)"
    elif not had_verdict_row:
        verdict = "not evaluable"
    elif any_reject:
        verdict = "rejected"
    elif all_support:
        verdict = "supported"
    else:
        verdict = "inconclusive"
    extra = ""
    if len(members) == 1:
        extra = f" (low-load set is {{{members[0]}}} VU only)"
    print(f"H1 verdict: {verdict}{extra}")


def slope(points):
    """Least-squares slope of p95 (ms) against VU. None when fewer than two points."""
    if len(points) < 2:
        return None
    xs = [vu for vu, _ in points]
    ys = [p95 for _, p95 in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom


def saturation_vu(by_vu):
    """Smallest VU whose median error rate exceeds 5%, or None when none does."""
    for vu in sorted(by_vu):
        if by_vu[vu]["error_rate_pct_median"] > H2_SATURATION_PCT:
            return vu
    return None


def h2_table(summary):
    index = {(r["mode"], r["endpoint"], int(r["users"]), r["framework"]): r for r in summary}
    groups = sorted({(mode, endpoint) for mode, endpoint, _, _ in index})
    print(f"\nH2: p95 slope on VU >= {H2_SLOPE_MIN_VU} still below saturation "
          f"(error <= {H2_SATURATION_PCT:g}%) is lower for NestJS; "
          f"error rate lower at VU >= 500; saturation (error > {H2_SATURATION_PCT:g}%) at a higher VU")
    print("p99 is listed per VU and is not an input to the slope")
    header = (f"{'mode':9} {'endpoint':8} {'VU':>5} {'p95 L':>8} {'p95 N':>8} "
              f"{'p99 L':>8} {'p99 N':>8} {'err L%':>7} {'err N%':>7}")
    print(header)
    print("-" * len(header))
    for mode, endpoint in groups:
        vus = sorted(
            vu for (m, e, vu, framework) in index
            if m == mode and e == endpoint and framework == "laravel"
            and (mode, endpoint, vu, "nestjs") in index
        )
        if not vus:
            print(f"{mode:9} {endpoint:8}        (no paired results yet)")
            continue
        lar = {vu: index[(mode, endpoint, vu, "laravel")] for vu in vus}
        nest = {vu: index[(mode, endpoint, vu, "nestjs")] for vu in vus}
        for vu in vus:
            print(f"{mode:9} {endpoint:8} {vu:>5} {lar[vu]['p95_ms_median']:>8.1f} "
                  f"{nest[vu]['p95_ms_median']:>8.1f} {lar[vu]['p99_ms_median']:>8.1f} "
                  f"{nest[vu]['p99_ms_median']:>8.1f} {lar[vu]['error_rate_pct_median']:>7.2f} "
                  f"{nest[vu]['error_rate_pct_median']:>7.2f}")

        full = [(vu, lar[vu]["p95_ms_median"], nest[vu]["p95_ms_median"]) for vu in vus]
        sat_l, sat_n = saturation_vu(lar), saturation_vu(nest)
        cut = min((s for s in (sat_l, sat_n) if s is not None), default=None)
        verdict_pts = [p for p in full if p[0] >= H2_SLOPE_MIN_VU and (cut is None or p[0] < cut)]
        slope_l = slope([(vu, p95) for vu, p95, _ in verdict_pts])
        slope_n = slope([(vu, p95) for vu, _, p95 in verdict_pts])
        full_l = slope([(vu, p95) for vu, p95, _ in full])
        full_n = slope([(vu, p95) for vu, _, p95 in full])

        high = [vu for vu in vus if vu >= 500]
        err_holds = bool(high) and all(nest[vu]["error_rate_pct_median"] < lar[vu]["error_rate_pct_median"] for vu in high)
        slope_holds = slope_l is not None and slope_n is not None and slope_n < slope_l
        rank = lambda s: math.inf if s is None else s
        sat_holds = rank(sat_n) > rank(sat_l)
        holds = slope_holds and err_holds and sat_holds

        def fmt_slope(value):
            return "n/d" if value is None else f"{value:.4f}"

        def fmt_sat(value):
            return "brak" if value is None else str(value)

        print(f"         slope full {fmt_slope(full_l)} / {fmt_slope(full_n)} ms/VU (L/N, not in the verdict), "
              f"VU>={H2_SLOPE_MIN_VU} below saturation {fmt_slope(slope_l)} / {fmt_slope(slope_n)}, "
              f"saturation {fmt_sat(sat_l)} / {fmt_sat(sat_n)}  "
              f"{'holds' if holds else 'rejected'}")


def git_hash():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT.parent.parent,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def load_runs(scenario_dir):
    run_dirs = sorted(p.parent for p in scenario_dir.glob("*/*/vu*/rep*/meta.json"))
    return [row for run_dir in run_dirs for row in summarise_run(run_dir)]


def coerce_run_row(row):
    out = dict(row)
    for key, cast in (("users", int), ("repetition", int), ("p95_ms", float),
                      ("throughput_rps", float), ("error_rate_pct", float),
                      ("app_cpu_share_pct", float), ("app_cpu_mean", float),
                      ("postgres_cpu_share_pct", float), ("postgres_cpu_mean", float)):
        if key in out and out[key] not in ("", None):
            out[key] = cast(out[key])
    return out


def load_s1_rows():
    """Prefer results/s1/runs.csv (the freeze input named in the methodology)."""
    csv_path = ROOT / "s1" / "runs.csv"
    if csv_path.exists():
        with csv_path.open(newline="") as fh:
            rows = [coerce_run_row(row) for row in csv.DictReader(fh)]
        if rows:
            return rows
    return load_runs(ROOT / "s1")


def freeze_h3_threshold():
    rows = load_s1_rows()
    if not rows:
        sys.exit(f"No complete S1 runs under {ROOT / 's1'} (need runs.csv or rep*/meta.json)")
    summary = aggregate(rows)
    members, diagnostics = lowload_set(summary, H1_ENDPOINTS)
    print_lowload(members, diagnostics, "S1")
    if not members:
        sys.exit("S1 low-load set is empty; cannot freeze Y")

    per_level = []
    s_vals = []
    for vu in members:
        lar = group_values(rows, "isolated", "EP1", vu, "laravel")
        nest = group_values(rows, "isolated", "EP1", vu, "nestjs")
        if len(lar) < 2 or len(nest) < 2:
            sys.exit(f"EP1 at {vu} VU needs at least two repetitions on both frameworks to compute SD")
        sd_l = statistics.stdev(lar)
        sd_n = statistics.stdev(nest)
        s = math.sqrt(sd_l ** 2 + sd_n ** 2)
        s_vals.append(s)
        per_level.append({"users": vu, "sd_l": sd_l, "sd_n": sd_n, "s": s, "n_l": len(lar), "n_n": len(nest)})

    y = max(H3_Y_FLOOR_MS, H3_Y_K * max(s_vals))
    peak = max(per_level, key=lambda row: row["s"])
    payload = {
        "y_ms": y,
        "floor_ms": H3_Y_FLOOR_MS,
        "k": H3_Y_K,
        "levels_used": members,
        "sd_l": peak["sd_l"],
        "sd_n": peak["sd_n"],
        "per_level": per_level,
        "formula": "Y = max(2 ms, 2 * max_v sqrt(SD_L(v)^2 + SD_N(v)^2)) on S1 isolated EP1 p95",
        "data_commit": git_hash(),
        "bootstrap_seed": BOOTSTRAP_SEED,
    }
    H3_THRESHOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    H3_THRESHOLD_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Y = {y:.3f} ms (floor {H3_Y_FLOOR_MS:g}, k={H3_Y_K:g}, max s={max(s_vals):.3f})")
    print(f"Wrote {H3_THRESHOLD_PATH}")


def load_h3_threshold():
    if not H3_THRESHOLD_PATH.exists():
        sys.exit(
            f"Missing {H3_THRESHOLD_PATH}. Freeze it after S1 with "
            "python3 scripts/summarize.py --freeze-h3-threshold"
        )
    return json.loads(H3_THRESHOLD_PATH.read_text())


def h3_table(summary, rows):
    threshold = load_h3_threshold()
    y = float(threshold["y_ms"])
    print(f"Y = {y:.3f} ms from {H3_THRESHOLD_PATH} (S1 levels {threshold.get('levels_used')})")

    pair_sets = {}
    for endpoint in H3_ENDPOINTS:
        members, diagnostics = lowload_set(summary, ("EP1", endpoint))
        pair_sets[endpoint] = members
        print_lowload(members, diagnostics, f"S3 pair (EP1, {endpoint})")
        verdict_vu, consistency_vu = pair_levels(members)
        if verdict_vu is not None:
            print(f"  {endpoint}: verdict {verdict_vu} VU, consistency {consistency_vu} VU")
        elif members:
            print(f"  {endpoint}: not evaluable (single level {members[0]} VU)")
        else:
            print(f"  {endpoint}: not evaluable (empty low-load set)")

    index = summary_index(summary)
    rng = random.Random(BOOTSTRAP_SEED)
    print("\nH3: D_k = (p95_L(k) − p95_N(k)) − (p95_L(EP1) − p95_N(EP1)), medians of 10 repetitions")
    header = (f"{'mode':9} {'endpoint':8} {'VU':>4} {'p95 L':>8} {'p95 N':>8} {'L/N':>6} "
              f"{'D_k':>8} {'CI lo':>8} {'CI hi':>8}  tag")
    print(header)
    print("-" * len(header))

    dk_at = {}
    ci_at = {}
    for (mode, endpoint, users, framework), lar in sorted(index.items()):
        if framework != "laravel" or endpoint not in H3_ENDPOINTS:
            continue
        nest = index.get((mode, endpoint, users, "nestjs"))
        ep1_l = index.get((mode, "EP1", users, "laravel"))
        ep1_n = index.get((mode, "EP1", users, "nestjs"))
        if nest is None or ep1_l is None or ep1_n is None:
            print(f"{mode:9} {endpoint:8} {users:>4}  (missing pair or EP1)")
            continue
        point = d_k(
            lar["p95_ms_median"], nest["p95_ms_median"],
            ep1_l["p95_ms_median"], ep1_n["p95_ms_median"],
        )
        dk_at[(mode, endpoint, users)] = point
        members = pair_sets[endpoint]
        verdict_vu, consistency_vu = pair_levels(members)
        in_set = users in members
        role = "observation"
        if verdict_vu is not None and users == verdict_vu:
            role = "verdict"
        elif consistency_vu is not None and users == consistency_vu:
            role = "consistency"
        lo = hi = None
        if in_set:
            boot = bootstrap_d_k(rows, mode, endpoint, users, rng)
            if boot:
                _, lo, hi = boot
                ci_at[(mode, endpoint, users)] = (lo, hi)
        lo_s = "n/d" if lo is None else f"{lo:.2f}"
        hi_s = "n/d" if hi is None else f"{hi:.2f}"
        ratio_s = fmt_ratio(ratio(lar["p95_ms_median"], nest["p95_ms_median"]))
        print(f"{mode:9} {endpoint:8} {users:>4} {lar['p95_ms_median']:>8.1f} {nest['p95_ms_median']:>8.1f} "
              f"{ratio_s:>6} {point:>8.2f} {lo_s:>8} {hi_s:>8}  {role}")

    modes = sorted({m for m, _, _ in dk_at}) or ["isolated"]
    for mode in modes:
        per_k = {}
        for endpoint in H3_ENDPOINTS:
            members = pair_sets[endpoint]
            verdict_vu, consistency_vu = pair_levels(members)
            if verdict_vu is None:
                per_k[endpoint] = "not evaluable"
                print(f"H3 {endpoint} ({mode}): not evaluable")
                continue
            ci = ci_at.get((mode, endpoint, verdict_vu))
            lo, hi = (None, None) if ci is None else ci
            per_k[endpoint] = classify_d_k(
                lo, hi, y,
                dk_at.get((mode, endpoint, verdict_vu)),
                dk_at.get((mode, endpoint, consistency_vu)),
            )
            print(f"H3 {endpoint} ({mode}): {per_k[endpoint]} "
                  f"at {verdict_vu} VU (consistency {consistency_vu} VU)")

        evaluable = {k: v for k, v in per_k.items() if v != "not evaluable"}
        if any(per_k[k] == "not evaluable" for k in H3_REQUIRED):
            verdict = "not evaluable"
        elif any(v == "rejected" for v in evaluable.values()):
            verdict = "rejected"
        elif evaluable and all(v == "supported" for v in evaluable.values()):
            verdict = "supported"
        else:
            verdict = "inconclusive"
        skipped = [k for k in H3_ENDPOINTS if per_k[k] == "not evaluable"]
        note = f" ({', '.join(skipped)} reported as observation)" if skipped else ""
        print(f"H3 verdict ({mode}): {verdict}{note}")


def print_query_counts(scenario_dir):
    files = sorted(scenario_dir.glob("query-count-*.txt"))
    print("\nSQL query count (out of band, not part of D_k):")
    if not files:
        print("  no query-count-*.txt; run scripts/query-count.sh <laravel|nestjs>")
        return
    for path in files:
        print(f"  {path.name}")
        for line in path.read_text().splitlines():
            print(f"    {line}")


def summarise_scenario(name):
    scenario_dir = ROOT / name
    rows = load_runs(scenario_dir)
    if not rows:
        sys.exit(f"No complete runs under {scenario_dir}")
    write_csv(scenario_dir / "runs.csv", rows)
    summary = aggregate(rows)
    write_csv(scenario_dir / "summary.csv", summary)
    print(f"{len(rows)} run rows -> {scenario_dir / 'runs.csv'}")
    print(f"{len(summary)} groups -> {scenario_dir / 'summary.csv'}")

    if name == "s1":
        h1_table(summary, rows)
    elif name == "s2" or name.startswith("s2-pool"):
        h2_table(summary)
    elif name == "s3":
        h3_table(summary, rows)
        print_query_counts(scenario_dir)
    flag_jmeter_cpu(summary)
    secondary_table(summary)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.split("\n\n")[1])
    if sys.argv[1] == "--freeze-h3-threshold":
        freeze_h3_threshold()
        return
    summarise_scenario(sys.argv[1])


if __name__ == "__main__":
    main()
