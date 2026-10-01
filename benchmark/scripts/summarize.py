#!/usr/bin/env python3
"""Summarise the runs written by scripts/run-scenario.sh.

Usage: python3 scripts/summarize.py <scenario>          e.g. ... s1

Writes results/<scenario>/runs.csv (one row per repetition and endpoint label) and
results/<scenario>/summary.csv (median and standard deviation across repetitions),
and for S1 prints the H1 verification table.

Definitions (Sections 3.3, 3.5 and 3.6 of the methodology):
- The ramp-up is excluded: the steady-state window starts rampup_s after the first
  measured sample and ends with the last completed sample.
- Percentiles use the nearest-rank method over all samples of a label in the window.
- Throughput counts successful samples only; the error rate counts every failed
  sample (assertion failures, HTTP errors and timeouts).
- CPU is reported as docker stats reports it (100% = one CPU) and as a share of the
  CPUs allocated to the application container.
- Delta between frameworks is relative to the mean of the two values, so neither
  framework is the reference: |a - b| / ((a + b) / 2).
"""

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "results"
SETUP_LABELS = {"SETUP_login"}
H1_LIMIT_PCT = 15.0
H1_ERROR_LIMIT_PCT = 1.0

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


def container_stats(stats_csv, window_wsl, cpus):
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
        role = next((r for r in ("app", "nginx", "postgres") if f"-{r}-" in name or name.endswith(r)), name)
        if not values["cpu"]:
            continue
        out[f"{role}_cpu_mean"] = statistics.fmean(values["cpu"])
        out[f"{role}_cpu_peak"] = max(values["cpu"])
        out[f"{role}_mem_mean_mib"] = statistics.fmean(values["mem"])
        out[f"{role}_mem_peak_mib"] = max(values["mem"])
    if "app_cpu_mean" in out:
        out["app_cpu_share_pct"] = out["app_cpu_mean"] / cpus
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
    )

    rows = []
    by_label = defaultdict(list)
    for s in steady:
        by_label[s["label"]].append(s)
    for label, group in sorted(by_label.items()):
        elapsed = sorted(s["elapsed"] for s in group)
        ok = sum(s["success"] for s in group)
        rows.append({
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
            "throughput_rps": ok / window_s,
            "error_rate_pct": 100 * (len(group) - ok) / len(group),
            **stats,
        })
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

    summary = []
    for key, group in sorted(groups.items()):
        out = dict(zip(keys, key))
        out["repetitions"] = len(group)
        metrics = [k for k in group[0] if k not in keys and k not in ("repetition", "samples", "window_s")]
        for metric in metrics:
            values = [r[metric] for r in group if metric in r]
            out[f"{metric}_median"] = statistics.median(values)
            out[f"{metric}_sd"] = statistics.stdev(values) if len(values) > 1 else 0.0
        summary.append(out)
    return summary


def rel_delta_pct(a, b):
    mean = (a + b) / 2
    return 0.0 if mean == 0 else 100 * abs(a - b) / mean


def h1_table(summary):
    index = {(r["mode"], r["endpoint"], r["users"], r["framework"]): r for r in summary}
    print(f"\nH1: |dp95| <= {H1_LIMIT_PCT:g}%, |dthroughput| <= {H1_LIMIT_PCT:g}%, "
          f"error rate < {H1_ERROR_LIMIT_PCT:g}% (medians, delta relative to the mean of both)")
    header = (f"{'mode':9} {'endpoint':8} {'VU':>4} {'p95 L':>8} {'p95 N':>8} {'dp95%':>7} "
              f"{'rps L':>9} {'rps N':>9} {'drps%':>7} {'err L%':>7} {'err N%':>7}  H1")
    print(header)
    print("-" * len(header))
    for (mode, endpoint, users, framework), lar in sorted(index.items()):
        if framework != "laravel":
            continue
        nest = index.get((mode, endpoint, users, "nestjs"))
        if nest is None:
            print(f"{mode:9} {endpoint:8} {users:>4}  (no NestJS results yet)")
            continue
        dp95 = rel_delta_pct(lar["p95_ms_median"], nest["p95_ms_median"])
        drps = rel_delta_pct(lar["throughput_rps_median"], nest["throughput_rps_median"])
        err_l, err_n = lar["error_rate_pct_median"], nest["error_rate_pct_median"]
        holds = dp95 <= H1_LIMIT_PCT and drps <= H1_LIMIT_PCT and max(err_l, err_n) < H1_ERROR_LIMIT_PCT
        print(f"{mode:9} {endpoint:8} {users:>4} {lar['p95_ms_median']:>8.1f} {nest['p95_ms_median']:>8.1f} "
              f"{dp95:>7.1f} {lar['throughput_rps_median']:>9.1f} {nest['throughput_rps_median']:>9.1f} "
              f"{drps:>7.1f} {err_l:>7.2f} {err_n:>7.2f}  {'holds' if holds else 'rejected'}")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.split("\n\n")[1])
    scenario_dir = ROOT / sys.argv[1]
    run_dirs = sorted(p.parent for p in scenario_dir.glob("*/*/vu*/rep*/meta.json"))
    if not run_dirs:
        sys.exit(f"No runs under {scenario_dir}")

    rows = [row for run_dir in run_dirs for row in summarise_run(run_dir)]
    if not rows:
        sys.exit("No complete runs to summarise")
    write_csv(scenario_dir / "runs.csv", rows)
    summary = aggregate(rows)
    write_csv(scenario_dir / "summary.csv", summary)
    print(f"{len(rows)} run rows -> {scenario_dir / 'runs.csv'}")
    print(f"{len(summary)} groups -> {scenario_dir / 'summary.csv'}")

    if sys.argv[1] == "s1":
        h1_table(summary)


if __name__ == "__main__":
    main()
