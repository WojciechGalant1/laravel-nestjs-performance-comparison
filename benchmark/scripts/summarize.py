#!/usr/bin/env python3
"""Summarise the runs written by scripts/run-scenario.sh.

Usage:
  python3 scripts/summarize.py <scenario>              e.g. ... s1
  python3 scripts/summarize.py --freeze-h3-threshold   after S1, before S3

Writes results/<scenario>/runs.csv (one row per repetition and endpoint label) and
results/<scenario>/summary.csv (median and standard deviation across repetitions).
S1 prints the H1 table (low-load set, bootstrap CI of |Δp95|). S2 prints the H2
table (bootstrap CI for the p95 slope ratio). S3 prints the H3 table (absolute D_k with signed-direction checks, bootstrap
CI, threshold Y from results/h3_threshold.json). Secondary Little's-law and CPU
per request figures are printed for every scenario and do not decide a verdict.

Definitions (Sections 3.3, 3.5 and 3.6 of the methodology):
- The ramp-up is excluded: the steady-state window starts rampup_s after the first
  measured sample and ends duration_s after that same first sample (the scheduled
  JMeter duration, not the last in-flight completion). Throughput is successful
  samples that started inside that interval, divided by (duration_s − rampup_s).
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
from summarize_common import (
    BOOTSTRAP_SEED, H1_ENDPOINTS, H1_ERROR_LIMIT_PCT, H1_LIMIT_PCT,
    H2_SATURATION_PCT, H2_SLOPE_MIN_VU, H3_CONSISTENCY_VU, H3_ENDPOINTS,
    H3_PRIMARY_ENDPOINT, H3_THRESHOLD_PATH, H3_VERDICT_VU, H3_Y_FLOOR_MS,
    H3_Y_K, JMETER_CPU_FLAG_PCT, LOWLOAD_CPU_SHARE_MAX,
    LOWLOAD_SCALING_MIN, PLANNED_VU, ROOT,
    d_k, fmt_number, fmt_ratio, group_values, metric_contrast, paired_summary,
    sensitivity_contrast, signed_gap, summary_index,
)
from summarize_data import (
    aggregate, coerce_run_row, load_runs, load_s1_rows, summarise_run, write_csv,
)
from summarize_stats import (
    bootstrap_d_k, bootstrap_rel_delta, bootstrap_slope_ratio, percentile,
    percentile_ci, ratio, rel_delta_pct, slope,
)

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
    if list(members[:2]) == [H3_CONSISTENCY_VU, H3_VERDICT_VU]:
        return H3_VERDICT_VU, H3_CONSISTENCY_VU
    return None, None


def classify_d_k(lo, hi, y, point_v, point_c, direction_v, direction_c):
    if (lo is None or hi is None or point_v is None or point_c is None
            or direction_v is None or direction_c is None):
        return "not evaluable"
    direction_ok = direction_v and direction_c
    if point_v <= 0 or point_c <= 0:
        direction_ok = False
    if lo > y and direction_ok:
        return "supported"
    if lo >= 0 and hi <= y:
        return "not supported (effect below Y)"
    if hi < 0:
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

        cpu_l, cpu_n = cell(lar, "cpu_per_request_ms_median"), cell(nest, "cpu_per_request_ms_median")
        p95_ratio = ratio(lar["p95_ms_median"], nest["p95_ms_median"])
        print(f"{mode:9} {endpoint:8} {users:>4} {lar['little_ms_median']:>8.2f} {nest['little_ms_median']:>8.2f} "
              f"{fmt_ratio(ratio(lar['little_ms_median'], nest['little_ms_median'])):>6} "
              f"{fmt_number(cpu_l):>7} {fmt_number(cpu_n):>7} {fmt_ratio(ratio(cpu_l, cpu_n)):>6} "
              f"{fmt_ratio(p95_ratio):>6} "
              f"{fmt_number(cell(lar, 'app_cpu_mean_median'), 0):>6} {fmt_number(cell(nest, 'app_cpu_mean_median'), 0):>6} "
              f"{fmt_number(cell(lar, 'nginx_cpu_mean_median'), 0):>6} {fmt_number(cell(nest, 'nginx_cpu_mean_median'), 0):>6} "
              f"{fmt_number(cell(lar, 'postgres_cpu_mean_median'), 0):>6} {fmt_number(cell(nest, 'postgres_cpu_mean_median'), 0):>6} "
              f"{fmt_number(cell(lar, 'jmeter_cpu_mean_median'), 0):>6} {fmt_number(cell(nest, 'jmeter_cpu_mean_median'), 0):>6}")


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
        if mode != "isolated":
            tag = "observation"
        elif not in_set:
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




def saturation_vu(by_vu):
    """Smallest VU whose median error rate exceeds 5%, or None when none does."""
    for vu in sorted(by_vu):
        if by_vu[vu]["error_rate_pct_median"] > H2_SATURATION_PCT:
            return vu
    return None




def h2_table(summary, rows):
    index = {(r["mode"], r["endpoint"], int(r["users"]), r["framework"]): r for r in summary}
    groups = sorted({(mode, endpoint) for mode, endpoint, _, _ in index})
    print(f"\nH2: bootstrap 95% CI for slope ratio s_L/s_N on VU >= {H2_SLOPE_MIN_VU}; "
          "this is the primary criterion")
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
        verdict_pts = [p for p in full if p[0] >= H2_SLOPE_MIN_VU]
        slope_l = slope([(vu, p95) for vu, p95, _ in verdict_pts])
        slope_n = slope([(vu, p95) for vu, _, p95 in verdict_pts])
        full_l = slope([(vu, p95) for vu, p95, _ in full])
        full_n = slope([(vu, p95) for vu, _, p95 in full])

        levels = [p[0] for p in verdict_pts]
        slope_ci = bootstrap_slope_ratio(
            rows, mode, endpoint, levels, random.Random(BOOTSTRAP_SEED)
        )
        if slope_ci is None:
            slope_status = "inconclusive"
        elif slope_ci[0] > 1:
            slope_status = "supported"
        elif slope_ci[1] < 1:
            slope_status = "rejected"
        else:
            slope_status = "inconclusive"
        high = [vu for vu in vus if vu >= 500]
        errors_observed = any(
            lar[vu]["error_rate_pct_median"] > 0 or nest[vu]["error_rate_pct_median"] > 0
            for vu in high
        )

        def fmt_slope(value):
            return "n/d" if value is None else f"{value:.4f}"

        def fmt_sat(value):
            return "brak" if value is None else str(value)

        ci_s = "n/d" if slope_ci is None else f"[{slope_ci[0]:.3f}, {slope_ci[1]:.3f}]"
        err_s = "reported" if errors_observed else "n/a (both zero)"
        print(f"         slope full {fmt_slope(full_l)} / {fmt_slope(full_n)} ms/VU (L/N, descriptive), "
              f"ratio CI {ci_s}, primary {slope_status}; "
              f"saturation {fmt_sat(sat_l)} / {fmt_sat(sat_n)}, errors {err_s} (supplementary)")


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


def print_ep2_observation(s3_rows):
    s1_rows = load_s1_rows()
    if not s1_rows:
        print("\nEP2 gradient observation from S1: unavailable (no S1 runs)")
        return
    s1_index = summary_index(aggregate(s1_rows))
    print("\nEP2 gradient observation from S1 (separate runs; descriptive only):")
    print(f"{'VU':>4} {'S1 EP1 L-N':>12} {'S1 EP2 L-N':>12} {'S3 EP1 L-N':>12} {'S3 EP4 L-N':>12}")
    s3_index = summary_index(aggregate(s3_rows)) if s3_rows else {}
    for users in (1, 2):
        gaps = {}
        for endpoint in ("EP1", "EP2"):
            pair = paired_summary(s1_index, "isolated", endpoint, users)
            if pair is None:
                gaps[endpoint] = "n/d"
            else:
                gaps[endpoint] = f"{pair.signed_gap():.2f}"
        for endpoint in ("EP1", "EP4"):
            pair = paired_summary(s3_index, "isolated", endpoint, users)
            if pair is None:
                gaps[f"s3_{endpoint}"] = "n/d"
            else:
                gaps[f"s3_{endpoint}"] = f"{pair.signed_gap():.2f}"
        print(f"{users:>4} {gaps['EP1']:>12} {gaps['EP2']:>12} "
              f"{gaps['s3_EP1']:>12} {gaps['s3_EP4']:>12}")


def h3_table(summary, rows):
    threshold = load_h3_threshold()
    y = float(threshold["y_ms"])
    print(f"Y = {y:.3f} ms from {H3_THRESHOLD_PATH} (S1 levels {threshold.get('levels_used')})")
    print_ep2_observation(rows)

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
    print("\nH3: D_k = |p95_L(k) − p95_N(k)| − |p95_L(EP1) − p95_N(EP1)|, medians of 10 repetitions")
    header = (f"{'mode':9} {'endpoint':8} {'VU':>4} {'p95 L':>8} {'p95 N':>8} {'L/N':>6} "
              f"{'D_k':>8} {'CI lo':>8} {'CI hi':>8}  tag")
    print(header)
    print("-" * len(header))

    dk_at = {}
    ci_at = {}
    signed_at = {}
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
        signed_at[(mode, endpoint, users)] = sensitivity_contrast(
            lar["p95_ms_median"], nest["p95_ms_median"],
            ep1_l["p95_ms_median"], ep1_n["p95_ms_median"],
        )
        members = pair_sets[endpoint]
        verdict_vu, consistency_vu = pair_levels(members)
        in_set = users in members
        role = "observation"
        if mode != "isolated":
            role = "observation"
        elif verdict_vu is not None and users == verdict_vu:
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
        if mode != "isolated":
            print(f"H3 {mode}: all results are observations; mixed mode does not determine the verdict")
            continue
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
            verdict_point = signed_at.get((mode, endpoint, verdict_vu))
            consistency_point = signed_at.get((mode, endpoint, consistency_vu))
            ep1_verdict = index.get((mode, "EP1", verdict_vu, "laravel"))
            ep1_verdict_n = index.get((mode, "EP1", verdict_vu, "nestjs"))
            ep1_consistency = index.get((mode, "EP1", consistency_vu, "laravel"))
            ep1_consistency_n = index.get((mode, "EP1", consistency_vu, "nestjs"))
            direction_v = None if verdict_point is None else verdict_point["signed_k"]
            direction_c = None if consistency_point is None else consistency_point["signed_k"]
            if ep1_verdict is not None and ep1_verdict_n is not None:
                direction_v = (
                    direction_v,
                    signed_gap(ep1_verdict["p95_ms_median"], ep1_verdict_n["p95_ms_median"]),
                )
            if ep1_consistency is not None and ep1_consistency_n is not None:
                direction_c = (
                    direction_c,
                    signed_gap(ep1_consistency["p95_ms_median"], ep1_consistency_n["p95_ms_median"]),
                )
            direction_v_ok = None if direction_v is None else (
                direction_v[0] != 0 and direction_v[1] != 0
                and (direction_v[0] > 0) == (direction_v[1] > 0)
            )
            direction_c_ok = None if direction_c is None else (
                direction_c[0] != 0 and direction_c[1] != 0
                and (direction_c[0] > 0) == (direction_c[1] > 0)
            )
            per_k[endpoint] = classify_d_k(
                lo, hi, y,
                dk_at.get((mode, endpoint, verdict_vu)),
                dk_at.get((mode, endpoint, consistency_vu)),
                direction_v_ok,
                direction_c_ok,
            )
            print(f"H3 {endpoint} ({mode}): {per_k[endpoint]} "
                  f"at {verdict_vu} VU (consistency {consistency_vu} VU)")

        primary = per_k[H3_PRIMARY_ENDPOINT]
        if primary == "not evaluable":
            verdict = "not evaluable"
        else:
            verdict = primary
        skipped = [k for k in H3_ENDPOINTS if k != H3_PRIMARY_ENDPOINT]
        note = f" ({', '.join(skipped)} reported as observation)" if skipped else ""
        print(f"H3 verdict ({mode}): {verdict}{note}")
        primary_members = pair_sets[H3_PRIMARY_ENDPOINT]
        primary_verdict_vu, primary_consistency_vu = pair_levels(primary_members)
        if primary_verdict_vu is not None and primary_consistency_vu is not None:
            print("  H3 EP4 sensitivity contrasts (absolute gap relative to EP1; no verdict):")
            for users in (primary_verdict_vu, primary_consistency_vu):
                mean_d = metric_contrast(index, mode, H3_PRIMARY_ENDPOINT, users, "mean_ms")
                little_d = metric_contrast(index, mode, H3_PRIMARY_ENDPOINT, users, "little_ms")
                mean_s = "n/d" if mean_d is None else f"{mean_d:.2f} ms"
                little_s = "n/d" if little_d is None else f"{little_d:.2f} ms"
                print(f"    {users} VU: mean response D={mean_s}; N/X D={little_s}")


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
        h2_table(summary, rows)
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
