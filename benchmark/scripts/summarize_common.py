#!/usr/bin/env python3
"""Shared constants and framework-pair helpers for benchmark summaries."""

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "results"
SETUP_LABELS = {"SETUP_login"}
H1_LIMIT_PCT = 15.0
H1_ERROR_LIMIT_PCT = 1.0
H1_ENDPOINTS = ("EP1", "EP2", "EP8")
H3_ENDPOINTS = ("EP4", "EP5", "EP6")
H3_PRIMARY_ENDPOINT = "EP4"
H3_VERDICT_VU = 2
H3_CONSISTENCY_VU = 1
H2_SATURATION_PCT = 5.0
H2_SLOPE_MIN_VU = 200
PLANNED_VU = (1, 2, 4, 10)
LOWLOAD_SCALING_MIN = 0.80
LOWLOAD_CPU_SHARE_MAX = 0.80
JMETER_CPU_FLAG_PCT = 80.0
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 20261002
H3_THRESHOLD_MS = 2.0

def fmt_ratio(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/d"
    return f"{value:.2f}x"

def fmt_number(value, digits=2, missing="n/d"):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return missing
    return f"{value:.{digits}f}"

def signed_gap(lar_p95, nest_p95):
    return lar_p95 - nest_p95

def d_k(lar_k, nest_k, lar_1, nest_1):
    return signed_gap(lar_k, nest_k) - signed_gap(lar_1, nest_1)

def sensitivity_contrast(lar_k, nest_k, lar_1, nest_1):
    signed_k = signed_gap(lar_k, nest_k)
    signed_1 = signed_gap(lar_1, nest_1)
    return {
        "signed_k": signed_k,
        "signed_1": signed_1,
        "signed_d": signed_k - signed_1,
    }

class FrameworkPair:
    def __init__(self, laravel, nestjs):
        self.laravel = laravel
        self.nestjs = nestjs

    def metric(self, name):
        laravel = self.laravel.get(f"{name}_median")
        nestjs = self.nestjs.get(f"{name}_median")
        if laravel is None or nestjs is None:
            return None
        return laravel, nestjs

    def signed_gap(self, metric="p95_ms"):
        values = self.metric(metric)
        return None if values is None else values[0] - values[1]

def paired_summary(index, mode, endpoint, users):
    laravel = index.get((mode, endpoint, int(users), "laravel"))
    nestjs = index.get((mode, endpoint, int(users), "nestjs"))
    if laravel is None or nestjs is None:
        return None
    return FrameworkPair(laravel, nestjs)


def metric_contrast(index, mode, endpoint, users, metric):
    endpoint_pair = paired_summary(index, mode, endpoint, users)
    baseline_pair = paired_summary(index, mode, "EP1", users)
    if endpoint_pair is None or baseline_pair is None:
        return None
    endpoint_values = endpoint_pair.metric(metric)
    baseline_values = baseline_pair.metric(metric)
    if endpoint_values is None or baseline_values is None:
        return None
    return (endpoint_values[0] - endpoint_values[1]) - (baseline_values[0] - baseline_values[1])


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
