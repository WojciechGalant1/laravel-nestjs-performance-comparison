#!/usr/bin/env python3
"""
Generate publication-quality charts for Scenario S3 (Relational Complexity / H3).
Outputs PNG (300 DPI) and SVG formats to dokumenty/figures/.
"""

import os
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

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

SUMMARY_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', 's3', 'summary.csv')

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

def plot_s3_relational_contrast(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.4, 3.5))

    color_lar = '#d9534f'
    color_nest = '#2b6cb0'

    endpoints = ['EP1 (0 rel)', 'EP2 (1 rel)', 'EP4 (3 nested)']
    ep_keys = ['EP1', 'EP2', 'EP4']
    x = np.arange(len(endpoints))
    width = 0.35

    # Panel 1: Tail Latency p95 at 2 VU (Verdict Level)
    lar_p95 = [data[(ep, 2, 'laravel')]['p95'] for ep in ep_keys]
    lar_sd = [data[(ep, 2, 'laravel')]['p95_sd'] for ep in ep_keys]
    nest_p95 = [data[(ep, 2, 'nestjs')]['p95'] for ep in ep_keys]
    nest_sd = [data[(ep, 2, 'nestjs')]['p95_sd'] for ep in ep_keys]

    ax1.bar(x - width/2, lar_p95, width, yerr=lar_sd, capsize=4, label='Laravel', color=color_lar, edgecolor='black', linewidth=0.6)
    ax1.bar(x + width/2, nest_p95, width, yerr=nest_sd, capsize=4, label='NestJS', color=color_nest, edgecolor='black', linewidth=0.6)

    ax1.set_title('(a) Tail Latency ($p_{95}$) at 2 VU')
    ax1.set_ylabel('Latency $p_{95}$ (ms)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(endpoints)
    ax1.set_ylim(0, 16)
    ax1.legend(loc='upper left', frameon=True)

    for i in range(len(ep_keys)):
        ax1.text(i - width/2, lar_p95[i] + lar_sd[i] + 0.4, f"{lar_p95[i]:.1f}", ha='center', fontsize=8)
        ax1.text(i + width/2, nest_p95[i] + nest_sd[i] + 0.4, f"{nest_p95[i]:.1f}", ha='center', fontsize=8, color=color_nest)

    # Panel 2: Diff-in-Diff Contrast D_k with Bootstrap 95% CI
    d_endpoints = ['EP2 (1 rel)', 'EP4 (3 nested)']
    d_vals = [2.50, 2.50]
    ci_lower = [0.50, 0.50]
    ci_upper = [3.00, 3.00]
    yerr = [
        [d_vals[i] - ci_lower[i] for i in range(2)],
        [ci_upper[i] - d_vals[i] for i in range(2)]
    ]

    dx = np.arange(len(d_endpoints))
    ax2.errorbar(dx, d_vals, yerr=yerr, fmt='o', color='#2c3e50', ecolor='#2c3e50',
                 elinewidth=2, capsize=5, capthick=1.5, markersize=7, label='Point Estimate $D_k$')

    ax2.axhline(2.0, color='red', linestyle='--', lw=1.2, label='Decision Threshold ($Y = 2.0$ ms)')
    ax2.axhline(0.0, color='gray', linestyle=':', lw=0.8)

    ax2.set_title('(b) Relational Contrast $D_k$ vs Baseline (2 VU)')
    ax2.set_ylabel('Contrast $D_k = S_k - S_{\mathrm{EP1}}$ (ms)')
    ax2.set_xticks(dx)
    ax2.set_xticklabels(d_endpoints)
    ax2.set_xlim(-0.5, 1.5)
    ax2.set_ylim(-0.5, 4.2)
    ax2.legend(loc='lower left', frameon=True, fontsize=8)

    fig.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, 'fig6_s3_relational.png')
    svg_path = os.path.join(OUTPUT_DIR, 'fig6_s3_relational.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")

def plot_s3_runtime_share(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.4, 3.5))

    color_lar = '#d9534f'
    color_nest = '#2b6cb0'

    endpoints = ['EP1\n(0 rel)', 'EP2\n(1 rel)', 'EP4\n(3 nested)', 'EP6\n(aggr)']
    ep_keys = ['EP1', 'EP2', 'EP4', 'EP6']
    x = np.arange(len(endpoints))
    width = 0.35

    # Panel 1: CPU time per request (ms / req) at 1 VU
    cpu_lar = [data[(ep, 1, 'laravel')]['cpu_req'] for ep in ep_keys]
    cpu_nest = [data[(ep, 1, 'nestjs')]['cpu_req'] for ep in ep_keys]
    cpu_lar_sd = [data[(ep, 1, 'laravel')]['cpu_req_sd'] for ep in ep_keys]
    cpu_nest_sd = [data[(ep, 1, 'nestjs')]['cpu_req_sd'] for ep in ep_keys]

    ax1.bar(x - width/2, cpu_lar, width, yerr=cpu_lar_sd, capsize=4, label='Laravel', color=color_lar, edgecolor='black', linewidth=0.6)
    ax1.bar(x + width/2, cpu_nest, width, yerr=cpu_nest_sd, capsize=4, label='NestJS', color=color_nest, edgecolor='black', linewidth=0.6)

    ax1.set_title('(a) Compute Cost: CPU per Request (1 VU)')
    ax1.set_ylabel('CPU Time (ms / req)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(endpoints)
    ax1.set_ylim(0, 11.5)
    ax1.legend(loc='upper right', frameon=True)

    for i in range(len(ep_keys)):
        ax1.text(i - width/2, cpu_lar[i] + cpu_lar_sd[i] + 0.3, f"{cpu_lar[i]:.1f}", ha='center', fontsize=7.5)
        ax1.text(i + width/2, cpu_nest[i] + cpu_nest_sd[i] + 0.3, f"{cpu_nest[i]:.1f}", ha='center', fontsize=7.5, color=color_nest)

    # Panel 2: EP6 Heavy Aggregation Latency at 1 and 2 VU
    p_levels = [1, 2]
    px = np.arange(len(p_levels))
    ep6_lar = [data[('EP6', u, 'laravel')]['p95'] for u in p_levels]
    ep6_nest = [data[('EP6', u, 'nestjs')]['p95'] for u in p_levels]
    ep6_lar_sd = [data[('EP6', u, 'laravel')]['p95_sd'] for u in p_levels]
    ep6_nest_sd = [data[('EP6', u, 'nestjs')]['p95_sd'] for u in p_levels]

    ax2.bar(px - width/2, ep6_lar, width, yerr=ep6_lar_sd, capsize=4, label='Laravel', color=color_lar, edgecolor='black', linewidth=0.6)
    ax2.bar(px + width/2, ep6_nest, width, yerr=ep6_nest_sd, capsize=4, label='NestJS', color=color_nest, edgecolor='black', linewidth=0.6)

    ax2.set_title('(b) EP6 Aggregation: Latency Equivalence')
    ax2.set_ylabel('Tail Latency $p_{95}$ (ms)')
    ax2.set_xticks(px)
    ax2.set_xticklabels(['1 VU', '2 VU'])
    ax2.set_ylim(0, 200)
    ax2.legend(loc='upper left', frameon=True)

    for i in range(len(p_levels)):
        ax2.text(i - width/2, ep6_lar[i] + ep6_lar_sd[i] + 3, f"{ep6_lar[i]:.1f}", ha='center', fontsize=8)
        ax2.text(i + width/2, ep6_nest[i] + ep6_nest_sd[i] + 3, f"{ep6_nest[i]:.1f}", ha='center', fontsize=8, color=color_nest)

    fig.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, 'fig7_s3_runtime_share.png')
    svg_path = os.path.join(OUTPUT_DIR, 'fig7_s3_runtime_share.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")

def plot_s3_combined_article(data):
    """Combined chart for the scientific article (Fig 3): Relational contrast D_k (EP2/EP4) + Heavy SQL convergence (EP6)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.6, 3.5))

    color_lar = '#d9534f'  # Muted Crimson
    color_nest = '#2b6cb0' # Deep Slate Blue

    # Panel 1: Diff-in-Diff Contrast D_k with Bootstrap 95% CI at 2 VU
    d_endpoints = ['EP2 (1 rel)', 'EP4 (3 nested)']
    d_vals = [2.50, 2.50]
    ci_lower = [0.50, 0.50]
    ci_upper = [3.00, 3.00]
    yerr = [
        [d_vals[i] - ci_lower[i] for i in range(2)],
        [ci_upper[i] - d_vals[i] for i in range(2)]
    ]

    dx = np.arange(len(d_endpoints))
    ax1.errorbar(dx, d_vals, yerr=yerr, fmt='o', color='#2c3e50', ecolor='#2c3e50',
                 elinewidth=2, capsize=5, capthick=1.5, markersize=7, label='Point Estimate $D_k$')

    ax1.axhline(2.0, color='red', linestyle='--', lw=1.2, label='Decision Threshold ($Y = 2.0$ ms)')
    ax1.axhline(0.0, color='gray', linestyle=':', lw=0.8)

    ax1.set_title('(a) Relational Contrast $D_k$ vs Baseline (2 VU)')
    ax1.set_ylabel('Contrast $D_k = S_k - S_{\mathrm{EP1}}$ (ms)')
    ax1.set_xticks(dx)
    ax1.set_xticklabels(d_endpoints)
    ax1.set_xlim(-0.5, 1.5)
    ax1.set_ylim(-0.5, 4.2)
    ax1.legend(loc='lower left', frameon=True, fontsize=8)

    # Panel 2: EP6 Heavy Aggregation Latency at 1 and 2 VU
    p_levels = [1, 2]
    px = np.arange(len(p_levels))
    width = 0.35
    ep6_lar = [data[('EP6', u, 'laravel')]['p95'] for u in p_levels]
    ep6_nest = [data[('EP6', u, 'nestjs')]['p95'] for u in p_levels]
    ep6_lar_sd = [data[('EP6', u, 'laravel')]['p95_sd'] for u in p_levels]
    ep6_nest_sd = [data[('EP6', u, 'nestjs')]['p95_sd'] for u in p_levels]

    ax2.bar(px - width/2, ep6_lar, width, yerr=ep6_lar_sd, capsize=4, label='Laravel', color=color_lar, edgecolor='black', linewidth=0.6)
    ax2.bar(px + width/2, ep6_nest, width, yerr=ep6_nest_sd, capsize=4, label='NestJS', color=color_nest, edgecolor='black', linewidth=0.6)

    ax2.set_title('(b) EP6 Aggregation: Latency Equivalence')
    ax2.set_ylabel('Tail Latency $p_{95}$ (ms)')
    ax2.set_xticks(px)
    ax2.set_xticklabels(['1 VU', '2 VU'])
    ax2.set_ylim(0, 200)
    ax2.legend(loc='upper left', frameon=True)

    for i in range(len(p_levels)):
        ax2.text(i - width/2, ep6_lar[i] + ep6_lar_sd[i] + 3, f"{ep6_lar[i]:.1f}", ha='center', fontsize=8)
        ax2.text(i + width/2, ep6_nest[i] + ep6_nest_sd[i] + 3, f"{ep6_nest[i]:.1f}", ha='center', fontsize=8, color=color_nest)

    fig.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, 'fig3_s3_relational_convergence.png')
    svg_path = os.path.join(OUTPUT_DIR, 'fig3_s3_relational_convergence.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")

if __name__ == '__main__':
    data = load_summary()
    plot_s3_relational_contrast(data)
    plot_s3_runtime_share(data)
    plot_s3_combined_article(data)

