#!/usr/bin/env python3
"""Loading, normalizing, and aggregating benchmark run data."""

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from summarize_common import ROOT, SETUP_LABELS, UNITS
from summarize_stats import percentile

def to_mib(value):
    for unit in sorted(UNITS, key=len, reverse=True):
        if value.endswith(unit):
            return float(value[: -len(unit)]) * UNITS[unit]
    raise ValueError(f"unknown memory unit: {value}")

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
    t0 = min(s["start"] for s in samples)
    window_start = t0 + meta["rampup_s"] * 1000
    window_end = t0 + meta["duration_s"] * 1000
    steady = [s for s in samples if window_start <= s["start"] < window_end]
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
            "mean_ms": statistics.mean(elapsed),
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
