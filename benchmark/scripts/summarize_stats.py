#!/usr/bin/env python3
"""Statistical helpers used by benchmark scenario reports."""

import math
import random
import statistics

from summarize_common import BOOTSTRAP_N, d_k, group_values

def percentile(sorted_values, p):
    rank = max(1, math.ceil(p / 100 * len(sorted_values)))
    return sorted_values[rank - 1]

def rel_delta_pct(a, b):
    mean = (a + b) / 2
    return 0.0 if mean == 0 else 100 * abs(a - b) / mean

def ratio(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b

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

def bootstrap_slope_ratio(rows, mode, endpoint, levels, rng):
    groups = {}
    for framework in ("laravel", "nestjs"):
        for vu in levels:
            values = group_values(rows, mode, endpoint, vu, framework, field="p95_ms")
            if not values:
                return None
            groups[(framework, vu)] = values

    ratios = []
    for _ in range(BOOTSTRAP_N):
        slopes = {}
        for framework in ("laravel", "nestjs"):
            points = [
                (vu, statistics.median(rng.choices(groups[(framework, vu)], k=len(groups[(framework, vu)]))))
                for vu in levels
            ]
            slopes[framework] = slope(points)
        if slopes["laravel"] is not None and slopes["nestjs"] not in (None, 0):
            ratios.append(slopes["laravel"] / slopes["nestjs"])
    return percentile_ci(ratios) if ratios else None
