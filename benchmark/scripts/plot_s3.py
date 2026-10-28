#!/usr/bin/env python3
"""
Generate publication-quality charts for Scenario S3 (Relational Complexity / H3).
Outputs PNG (300 DPI) and SVG formats to dokumenty/figures/.

The relational contrast D_k is computed from results/s3/runs.csv (percentile bootstrap,
same procedure as scripts/summarize.py). The primary H3 contrast is EP2 against its
same-table control EP2b; contrasts against EP1 are kept for comparison (legacy,
confounded by table and payload size). Panels are skipped gracefully when EP2b has not
been measured yet.
"""

import os
import csv
import random
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from summarize_common import BOOTSTRAP_SEED, H3_THRESHOLD_MS  # noqa: E402
from summarize_data import coerce_run_row  # noqa: E402
from summarize_stats import bootstrap_d_k  # noqa: E402

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial', 'Helvetica'],
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 12,
    'lines.linewidth': 1.6,
    'lines.markersize': 6,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--',
    'figure.autolayout': True
})

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'dokumenty', 'figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', 's3')
SUMMARY_CSV = os.path.join(RESULTS_DIR, 'summary.csv')
RUNS_CSV = os.path.join(RESULTS_DIR, 'runs.csv')

COLOR_LAR = '#d9534f'   # Muted Crimson
COLOR_NEST = '#2b6cb0'  # Deep Slate Blue

# (endpoint key, tick label); EP2b is the same-table baseline.
LATENCY_ENDPOINTS = [
    ('EP2b', 'EP2b\n(0 rel,\nbaseline)'),
    ('EP2', 'EP2\n(1 rel)'),
    ('EP4', 'EP4\n(3 nested)'),
]
CPU_ENDPOINTS = LATENCY_ENDPOINTS + [('EP6', 'EP6\n(aggr)')]

# (endpoint, reference, label, marker colour)
CONTRASTS = [
    ('EP2', 'EP2b', 'EP2 vs EP2b\n(1:N relation)', '#2c3e50'),
    ('EP4', 'EP2b', 'EP4 vs EP2b\n(3-level nested)', '#2b6cb0'),
]


def load_summary():
    data = {}
    with open(SUMMARY_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            key = (r['endpoint'], int(r['users']), r['framework'])
            data[key] = {
                'rps': float(r['throughput_rps_median']),
                'rps_sd': float(r['throughput_rps_sd']),
                'p95': float(r['p95_ms_median']),
                'p95_sd': float(r['p95_ms_sd']),
                'p50': float(r['p50_ms_median']),
                'cpu_req': float(r['cpu_per_request_ms_median']),
                'cpu_req_sd': float(r['cpu_per_request_ms_sd']),
                'app_cpu': float(r['app_cpu_share_pct_median']) * 100.0,
                'pg_cpu': float(r['postgres_cpu_share_pct_median']) * 100.0,
            }
    return data


def load_runs():
    with open(RUNS_CSV, 'r', encoding='utf-8', newline='') as f:
        return [coerce_run_row(r) for r in csv.DictReader(f)]


def compute_contrasts(rows, users=2):
    """Return [(label, colour, point, lo, hi)] for contrasts whose inputs are measured."""
    out = []
    for endpoint, reference, label, colour in CONTRASTS:
        rng = random.Random(BOOTSTRAP_SEED)
        res = bootstrap_d_k(rows, 'isolated', endpoint, users, rng, reference=reference)
        if res is None:
            continue
        point, lo, hi = res
        out.append((label, colour, point, lo, hi))
    return out


def available(data, endpoints, users):
    return [(k, lbl) for k, lbl in endpoints
            if (k, users, 'laravel') in data and (k, users, 'nestjs') in data]


def draw_contrast_panel(ax, contrasts, title):
    ax.axhline(H3_THRESHOLD_MS, color='red', linestyle='--', lw=1.2,
               label=f'Decision Threshold ($Y = {H3_THRESHOLD_MS:.1f}$ ms)')
    ax.axhline(0.0, color='gray', linestyle=':', lw=0.8)
    ax.set_title(title)
    ax.set_ylabel('Contrast $D_k = S_k - S_{\\mathrm{ref}}$ (ms)')
    if not contrasts:
        ax.text(0.5, 0.5, 'no contrast data', ha='center', va='center', transform=ax.transAxes)
        return
    dx = np.arange(len(contrasts))
    for i, (_, colour, point, lo, hi) in enumerate(contrasts):
        ax.errorbar(i, point, yerr=[[point - lo], [hi - point]], fmt='o', color=colour,
                    ecolor=colour, elinewidth=2, capsize=5, capthick=1.5, markersize=7,
                    label='Point estimate and 95% CI' if i == 0 else None)
    ax.set_xticks(dx)
    ax.set_xticklabels([c[0] for c in contrasts], fontsize=8)
    ax.set_xlim(-0.5, len(contrasts) - 0.5)
    lows = [c[3] for c in contrasts] + [0.0]
    highs = [c[4] for c in contrasts] + [H3_THRESHOLD_MS]
    ax.set_ylim(min(lows) - 1.0, max(highs) + 1.0)
    ax.legend(loc='lower left', frameon=True, fontsize=8)


def grouped_bars(ax, data, endpoints, users, key, err_key, ymax_pad, fmt_size=8):
    x = np.arange(len(endpoints))
    width = 0.35
    lar = [data[(ep, users, 'laravel')][key] for ep, _ in endpoints]
    lar_sd = [data[(ep, users, 'laravel')][err_key] for ep, _ in endpoints]
    nest = [data[(ep, users, 'nestjs')][key] for ep, _ in endpoints]
    nest_sd = [data[(ep, users, 'nestjs')][err_key] for ep, _ in endpoints]

    ax.bar(x - width / 2, lar, width, yerr=lar_sd, capsize=4, label='Laravel', color=COLOR_LAR, edgecolor='black', linewidth=0.6)
    ax.bar(x + width / 2, nest, width, yerr=nest_sd, capsize=4, label='NestJS', color=COLOR_NEST, edgecolor='black', linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([lbl for _, lbl in endpoints])
    top = max(l + s for l, s in zip(lar, lar_sd))
    ax.set_ylim(0, top * 1.15 + ymax_pad)
    for i in range(len(endpoints)):
        ax.text(i - width / 2, lar[i] + lar_sd[i] + ymax_pad / 3, f"{lar[i]:.1f}", ha='center', fontsize=fmt_size)
        ax.text(i + width / 2, nest[i] + nest_sd[i] + ymax_pad / 3, f"{nest[i]:.1f}", ha='center', fontsize=fmt_size, color=COLOR_NEST)


def save(fig, name):
    png_path = os.path.join(OUTPUT_DIR, f'{name}.png')
    svg_path = os.path.join(OUTPUT_DIR, f'{name}.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")


def plot_s3_relational_contrast(data, rows):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 3.8))

    # Panel 1: Tail Latency p95 at 2 VU (Verdict Level)
    endpoints = available(data, LATENCY_ENDPOINTS, 2)
    grouped_bars(ax1, data, endpoints, 2, 'p95', 'p95_sd', 1.0)
    ax1.set_title('(a) Tail Latency ($p_{95}$) at 2 VU')
    ax1.set_ylabel('Latency $p_{95}$ (ms)')
    ax1.legend(loc='upper left', frameon=True)

    # Panel 2: Diff-in-Diff Contrast D_k with Bootstrap 95% CI
    draw_contrast_panel(ax2, compute_contrasts(rows, 2), '(b) Relational Contrast $D_k$ (2 VU)')

    fig.tight_layout()
    save(fig, 'fig6_s3_relational')


def plot_s3_runtime_share(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 3.8))

    # Panel 1: CPU time per request (ms / req) at 1 VU
    endpoints = available(data, CPU_ENDPOINTS, 1)
    grouped_bars(ax1, data, endpoints, 1, 'cpu_req', 'cpu_req_sd', 0.9, fmt_size=7.5)
    ax1.set_title('(a) Compute Cost: CPU per Request (1 VU)')
    ax1.set_ylabel('CPU Time (ms / req)')
    ax1.legend(loc='upper right', frameon=True)

    # Panel 2: EP6 Heavy Aggregation Latency at 1 and 2 VU
    draw_ep6_panel(ax2, data)

    fig.tight_layout()
    save(fig, 'fig7_s3_runtime_share')


def draw_ep6_panel(ax, data):
    p_levels = [1, 2]
    px = np.arange(len(p_levels))
    width = 0.35
    ep6_lar = [data[('EP6', u, 'laravel')]['p95'] for u in p_levels]
    ep6_nest = [data[('EP6', u, 'nestjs')]['p95'] for u in p_levels]
    ep6_lar_sd = [data[('EP6', u, 'laravel')]['p95_sd'] for u in p_levels]
    ep6_nest_sd = [data[('EP6', u, 'nestjs')]['p95_sd'] for u in p_levels]

    ax.bar(px - width / 2, ep6_lar, width, yerr=ep6_lar_sd, capsize=4, label='Laravel', color=COLOR_LAR, edgecolor='black', linewidth=0.6)
    ax.bar(px + width / 2, ep6_nest, width, yerr=ep6_nest_sd, capsize=4, label='NestJS', color=COLOR_NEST, edgecolor='black', linewidth=0.6)

    ax.set_title('(b) EP6 Aggregation: Relative Latency Gap')
    ax.set_ylabel('Tail Latency $p_{95}$ (ms)')
    ax.set_xticks(px)
    ax.set_xticklabels(['1 VU', '2 VU'])
    ax.set_ylim(0, 200)
    ax.legend(loc='upper left', frameon=True)

    for i in range(len(p_levels)):
        ax.text(i - width / 2, ep6_lar[i] + ep6_lar_sd[i] + 3, f"{ep6_lar[i]:.1f}", ha='center', fontsize=8)
        ax.text(i + width / 2, ep6_nest[i] + ep6_nest_sd[i] + 3, f"{ep6_nest[i]:.1f}", ha='center', fontsize=8, color=COLOR_NEST)


def plot_s3_combined_article(data, rows):
    """Combined chart for the scientific article (Fig 3): relational contrast D_k + EP6 latency."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.8))

    draw_contrast_panel(ax1, compute_contrasts(rows, 2), '(a) Relational Contrast $D_k$ (2 VU)')
    draw_ep6_panel(ax2, data)

    fig.tight_layout()
    save(fig, 'fig3_s3_relational_convergence')


if __name__ == '__main__':
    data = load_summary()
    rows = load_runs()
    plot_s3_relational_contrast(data, rows)
    plot_s3_runtime_share(data)
    plot_s3_combined_article(data, rows)
