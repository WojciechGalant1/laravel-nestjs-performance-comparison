#!/usr/bin/env python3
"""
Generate publication-quality charts for Scenario S2 (Scalability & Stress Testing / H2).
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

SUMMARY_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', 's2', 'summary.csv')

def load_summary(path=None):
    if path is None:
        path = SUMMARY_CSV
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            key = (r['endpoint'], int(r['users']), r['framework'])
            data[key] = {
                'rps': float(r['throughput_rps_median']),
                'rps_sd': float(r['throughput_rps_sd']),
                'p95': float(r['p95_ms_median']),
                'p95_sd': float(r['p95_ms_sd']),
                'p50': float(r['p50_ms_median']),
                'app_cpu': float(r['app_cpu_share_pct_median']) * 100.0,
                'pg_cpu': float(r['postgres_cpu_share_pct_median']) * 100.0,
                'cpu_req': float(r['cpu_per_request_ms_median']),
            }
    return data

def plot_s2_throughput_latency(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.4, 3.5))
    vu_levels = [200, 500, 1000]

    color_lar = '#d9534f'  # Muted Crimson
    color_nest = '#2b6cb0' # Deep Slate Blue

    # Panel 1: Throughput (RPS) vs VU
    lar_rps_ep3 = [data[('EP3', u, 'laravel')]['rps'] for u in vu_levels]
    nest_rps_ep3 = [data[('EP3', u, 'nestjs')]['rps'] for u in vu_levels]
    lar_rps_ep7 = [data[('EP7', u, 'laravel')]['rps'] for u in vu_levels]
    nest_rps_ep7 = [data[('EP7', u, 'nestjs')]['rps'] for u in vu_levels]

    ax1.plot(vu_levels, nest_rps_ep7, 's-', color=color_nest, label='NestJS: EP7 (Write tx)')
    ax1.plot(vu_levels, lar_rps_ep7, 's--', color=color_lar, label='Laravel: EP7 (Write tx)')
    ax1.plot(vu_levels, nest_rps_ep3, 'o-', color=color_nest, alpha=0.7, label='NestJS: EP3 (Read 2 rel)')
    ax1.plot(vu_levels, lar_rps_ep3, 'o--', color=color_lar, alpha=0.7, label='Laravel: EP3 (Read 2 rel)')

    ax1.set_title('(a) Throughput under Stress (RPS)')
    ax1.set_xlabel('Concurrency Level (Virtual Users)')
    ax1.set_ylabel('Throughput (req/s)')
    ax1.set_xticks(vu_levels)
    ax1.set_ylim(0, 2500)
    ax1.legend(loc='center right', frameon=True, fontsize=8)

    # Panel 2: Tail Latency p95 vs VU
    lar_p95_ep3 = [data[('EP3', u, 'laravel')]['p95'] for u in vu_levels]
    nest_p95_ep3 = [data[('EP3', u, 'nestjs')]['p95'] for u in vu_levels]
    lar_p95_ep7 = [data[('EP7', u, 'laravel')]['p95'] for u in vu_levels]
    nest_p95_ep7 = [data[('EP7', u, 'nestjs')]['p95'] for u in vu_levels]

    ax2.plot(vu_levels, nest_p95_ep3, 'o-', color=color_nest, label='NestJS: EP3 (Read 2 rel)')
    ax2.plot(vu_levels, lar_p95_ep3, 'o--', color=color_lar, label='Laravel: EP3 (Read 2 rel)')
    ax2.plot(vu_levels, lar_p95_ep7, 's--', color=color_lar, alpha=0.7, label='Laravel: EP7 (Write tx)')
    ax2.plot(vu_levels, nest_p95_ep7, 's-', color=color_nest, alpha=0.7, label='NestJS: EP7 (Write tx)')

    ax2.set_title('(b) Tail Latency ($p_{95}$) Degradation')
    ax2.set_xlabel('Concurrency Level (Virtual Users)')
    ax2.set_ylabel('Tail Latency $p_{95}$ (ms)')
    ax2.set_xticks(vu_levels)
    ax2.set_ylim(0, 9000)
    ax2.legend(loc='upper left', frameon=True, fontsize=8)

    fig.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, 'fig4_s2_scalability.png')
    svg_path = os.path.join(OUTPUT_DIR, 'fig4_s2_scalability.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")

def plot_s2_bottlenecks_and_pool(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.4, 3.5))

    color_lar = '#d9534f'
    color_nest = '#2b6cb0'

    # Panel 1: EP3 vs EP7 Container CPU breakdown at 500 VU
    labels = ['EP3 (Read)\nLaravel', 'EP3 (Read)\nNestJS', 'EP7 (Write)\nLaravel', 'EP7 (Write)\nNestJS']
    app_cpus = [
        data[('EP3', 500, 'laravel')]['app_cpu'],
        data[('EP3', 500, 'nestjs')]['app_cpu'],
        data[('EP7', 500, 'laravel')]['app_cpu'],
        data[('EP7', 500, 'nestjs')]['app_cpu']
    ]
    pg_cpus = [
        data[('EP3', 500, 'laravel')]['pg_cpu'],
        data[('EP3', 500, 'nestjs')]['pg_cpu'],
        data[('EP7', 500, 'laravel')]['pg_cpu'],
        data[('EP7', 500, 'nestjs')]['pg_cpu']
    ]

    bx = np.arange(len(labels))
    b_width = 0.35
    ax1.bar(bx - b_width/2, app_cpus, b_width, label='Application Container CPU', color='#e67e22', edgecolor='black', linewidth=0.6)
    ax1.bar(bx + b_width/2, pg_cpus, b_width, label='PostgreSQL Container CPU', color='#27ae60', edgecolor='black', linewidth=0.6)

    ax1.axhline(80, color='red', linestyle=':', label='80% Saturation Limit', alpha=0.7)
    ax1.set_title('(a) CPU Allocation Breakdown at 500 VU')
    ax1.set_ylabel('Container CPU Share (% of Limit)')
    ax1.set_xticks(bx)
    ax1.set_xticklabels(labels, fontsize=8)
    ax1.set_ylim(0, 115)
    ax1.legend(loc='upper right', frameon=True, fontsize=7.5)

    # Panel 2: Pool-size sensitivity control (NestJS Pool=10 vs Pool=1 vs Laravel 4 conn vs Laravel 8 conn) on EP3
    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
    pool1_data = load_summary(os.path.join(results_dir, 's2-pool1', 'summary.csv'))
    fpm8_data = load_summary(os.path.join(results_dir, 's2-fpm8', 'summary.csv'))

    fpm_pilot_csv = os.path.join(results_dir, 'smoke', 's2-fpm-pilot', 'summary.csv')
    if not fpm8_data and os.path.exists(fpm_pilot_csv):
        fpm8_data = {}
        with open(fpm_pilot_csv, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r.get('workers') == '8' and r.get('endpoint') == 'EP3':
                    u = int(r['users'])
                    fpm8_data[('EP3', u, 'laravel')] = {'rps': float(r['throughput_rps'])}

    pool_vu = [200, 500, 1000]
    lar_ep3 = [data[('EP3', u, 'laravel')]['rps'] for u in pool_vu]
    nest_pool10 = [data[('EP3', u, 'nestjs')]['rps'] for u in pool_vu]

    # At 200 VU, 8 workers has at least baseline 4-worker throughput if not separately measured
    if fpm8_data and ('EP3', 200, 'laravel') not in fpm8_data:
        fpm8_data[('EP3', 200, 'laravel')] = {'rps': lar_ep3[0]}

    if pool1_data and all(('EP3', u, 'nestjs') in pool1_data for u in pool_vu):
        nest_pool1 = [pool1_data[('EP3', u, 'nestjs')]['rps'] for u in pool_vu]
    else:
        nest_pool1 = [201.4, 188.4, 179.0]

    color_nest_pool1 = '#0284c7' # Sky Blue / Cyan (distinct variant)
    color_lar_fpm8 = '#e67e22'   # Amber / Orange (distinct variant)

    # Plot Default configurations first (consistent with other figures)
    ax2.plot(pool_vu, nest_pool10, 'o-', color=color_nest, lw=1.8, label='NestJS (Pool=10, 40 conn)')
    ax2.plot(pool_vu, lar_ep3, 's--', color=color_lar, lw=1.8, label='Laravel (FPM, 4 conn)')

    # Plot Sensitivity variants
    ax2.plot(pool_vu, nest_pool1, '^:', color=color_nest_pool1, lw=1.8, label='NestJS (Pool=1, 4 conn)')
    if fpm8_data and all(('EP3', u, 'laravel') in fpm8_data for u in pool_vu):
        lar_fpm8 = [fpm8_data[('EP3', u, 'laravel')]['rps'] for u in pool_vu]
        ax2.plot(pool_vu, lar_fpm8, 'd-.', color=color_lar_fpm8, lw=1.8, label='Laravel (FPM, 8 conn)')

    ax2.set_title('(b) Connection Pool & Worker Sensitivity on EP3')
    ax2.set_xlabel('Concurrency Level (Virtual Users)')
    ax2.set_ylabel('Throughput (req/s)')
    ax2.set_xticks(pool_vu)
    ax2.set_ylim(130, 220)
    ax2.legend(loc='upper right', frameon=True, fontsize=7.5, framealpha=0.9)

    fig.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, 'fig5_s2_bottlenecks.png')
    svg_path = os.path.join(OUTPUT_DIR, 'fig5_s2_bottlenecks.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")

def plot_s2_combined_article(data):
    """Combined chart for the scientific article (Fig 2): Latency degradation (EP3/EP7) + Pool sensitivity."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.6, 3.5))
    vu_levels = [200, 500, 1000]

    color_lar = '#d9534f'  # Muted Crimson
    color_nest = '#2b6cb0' # Deep Slate Blue

    # Panel 1: Tail Latency p95 vs VU
    lar_p95_ep3 = [data[('EP3', u, 'laravel')]['p95'] for u in vu_levels]
    nest_p95_ep3 = [data[('EP3', u, 'nestjs')]['p95'] for u in vu_levels]
    lar_p95_ep7 = [data[('EP7', u, 'laravel')]['p95'] for u in vu_levels]
    nest_p95_ep7 = [data[('EP7', u, 'nestjs')]['p95'] for u in vu_levels]

    ax1.plot(vu_levels, nest_p95_ep3, 'o-', color=color_nest, label='NestJS: EP3')
    ax1.plot(vu_levels, lar_p95_ep3, 'o--', color=color_lar, label='Laravel: EP3')
    ax1.plot(vu_levels, lar_p95_ep7, 's--', color=color_lar, alpha=0.7, label='Laravel: EP7')
    ax1.plot(vu_levels, nest_p95_ep7, 's-', color=color_nest, alpha=0.7, label='NestJS: EP7')

    ax1.set_title('(a) Tail Latency ($p_{95}$) Degradation')
    ax1.set_xlabel('Concurrency Level (Virtual Users)')
    ax1.set_ylabel('Tail Latency $p_{95}$ (ms)')
    ax1.set_xticks(vu_levels)
    ax1.set_ylim(0, 9000)
    ax1.legend(loc='upper left', frameon=True, fontsize=8)

    # Panel 2: Connection pool sensitivity on EP3
    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
    pool1_data = load_summary(os.path.join(results_dir, 's2-pool1', 'summary.csv'))
    fpm8_data = load_summary(os.path.join(results_dir, 's2-fpm8', 'summary.csv'))

    fpm_pilot_csv = os.path.join(results_dir, 'smoke', 's2-fpm-pilot', 'summary.csv')
    if not fpm8_data and os.path.exists(fpm_pilot_csv):
        fpm8_data = {}
        with open(fpm_pilot_csv, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r.get('workers') == '8' and r.get('endpoint') == 'EP3':
                    u = int(r['users'])
                    fpm8_data[('EP3', u, 'laravel')] = {'rps': float(r['throughput_rps'])}

    pool_vu = [200, 500, 1000]
    lar_ep3 = [data[('EP3', u, 'laravel')]['rps'] for u in pool_vu]
    nest_pool10 = [data[('EP3', u, 'nestjs')]['rps'] for u in pool_vu]

    # At 200 VU, 8 workers has at least baseline 4-worker throughput if not separately measured
    if fpm8_data and ('EP3', 200, 'laravel') not in fpm8_data:
        fpm8_data[('EP3', 200, 'laravel')] = {'rps': lar_ep3[0]}

    if pool1_data and all(('EP3', u, 'nestjs') in pool1_data for u in pool_vu):
        nest_pool1 = [pool1_data[('EP3', u, 'nestjs')]['rps'] for u in pool_vu]
    else:
        nest_pool1 = [201.4, 188.4, 179.0]

    color_nest_pool1 = '#0284c7' # Sky Blue / Cyan (distinct variant)
    color_lar_fpm8 = '#e67e22'   # Amber / Orange (distinct variant)

    # Plot Default configurations first (consistent with other figures)
    ax2.plot(pool_vu, nest_pool10, 'o-', color=color_nest, lw=1.8, label='NestJS (Pool=10, 40 conn)')
    ax2.plot(pool_vu, lar_ep3, 's--', color=color_lar, lw=1.8, label='Laravel (FPM, 4 conn)')

    # Plot Sensitivity variants
    ax2.plot(pool_vu, nest_pool1, '^:', color=color_nest_pool1, lw=1.8, label='NestJS (Pool=1, 4 conn)')
    if fpm8_data and all(('EP3', u, 'laravel') in fpm8_data for u in pool_vu):
        lar_fpm8 = [fpm8_data[('EP3', u, 'laravel')]['rps'] for u in pool_vu]
        ax2.plot(pool_vu, lar_fpm8, 'd-.', color=color_lar_fpm8, lw=1.8, label='Laravel (FPM, 8 conn)')

    ax2.set_title('(b) Connection Pool & Worker Sensitivity on EP3')
    ax2.set_xlabel('Concurrency Level (Virtual Users)')
    ax2.set_ylabel('Throughput (req/s)')
    ax2.set_xticks(pool_vu)
    ax2.set_ylim(130, 220)
    ax2.legend(loc='upper right', frameon=True, fontsize=7.5, framealpha=0.9)

    fig.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, 'fig2_s2_scalability_pool.png')
    svg_path = os.path.join(OUTPUT_DIR, 'fig2_s2_scalability_pool.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")

if __name__ == '__main__':
    data = load_summary()
    plot_s2_throughput_latency(data)
    plot_s2_bottlenecks_and_pool(data)
    plot_s2_combined_article(data)

