#!/usr/bin/env python3
"""
Generate publication-quality charts for Scenario S1 (Baseline Performance / H1).
Outputs PNG (300 DPI) and SVG formats to dokumenty/figures/.
"""

import os
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Set academic publication style
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
    'lines.linewidth': 1.5,
    'lines.markersize': 6,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--',
    'figure.autolayout': True
})

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'dokumenty', 'figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

SUMMARY_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', 's1', 'summary.csv')

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
                'mean': float(r['mean_ms_median']),
                'mean_sd': float(r['mean_ms_sd']),
                'cpu_req': float(r['cpu_per_request_ms_median']),
                'cpu_req_sd': float(r['cpu_per_request_ms_sd']),
                'mem_pk': float(r['app_mem_peak_mib_median']),
                'mem_pk_sd': float(r['app_mem_peak_mib_sd']),
                'cpu_pct': float(r['app_cpu_share_pct_median']) * 100.0,
            }
    return data

def plot_throughput(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.4), sharey=False)
    vu_levels = [1, 2, 4, 10]
    x = np.arange(len(vu_levels))
    width = 0.35

    color_lar = '#d9534f'  # Muted Crimson
    color_nest = '#2b6cb0' # Deep Slate Blue

    # Panel 1: EP1 Read
    lar_rps_ep1 = [data[('EP1', u, 'laravel')]['rps'] for u in vu_levels]
    lar_sd_ep1 = [data[('EP1', u, 'laravel')]['rps_sd'] for u in vu_levels]
    nest_rps_ep1 = [data[('EP1', u, 'nestjs')]['rps'] for u in vu_levels]
    nest_sd_ep1 = [data[('EP1', u, 'nestjs')]['rps_sd'] for u in vu_levels]

    ax1.bar(x - width/2, lar_rps_ep1, width, yerr=lar_sd_ep1, capsize=4, label='Laravel (PHP-FPM)', color=color_lar, edgecolor='black', linewidth=0.6)
    ax1.bar(x + width/2, nest_rps_ep1, width, yerr=nest_sd_ep1, capsize=4, label='NestJS (Fastify)', color=color_nest, edgecolor='black', linewidth=0.6)

    ax1.set_title('(a) EP1: Single-Table Read (GET)')
    ax1.set_xlabel('Concurrency Level (Virtual Users)')
    ax1.set_ylabel('Throughput (req/s)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(['1 VU', '2 VU', '4 VU*', '10 VU*'])
    ax1.legend(loc='upper left', frameon=True)
    ax1.set_ylim(0, 4200)

    # Panel 2: EP5 Update
    lar_rps_ep5 = [data[('EP5', u, 'laravel')]['rps'] for u in vu_levels]
    lar_sd_ep5 = [data[('EP5', u, 'laravel')]['rps_sd'] for u in vu_levels]
    nest_rps_ep5 = [data[('EP5', u, 'nestjs')]['rps'] for u in vu_levels]
    nest_sd_ep5 = [data[('EP5', u, 'nestjs')]['rps_sd'] for u in vu_levels]

    ax2.bar(x - width/2, lar_rps_ep5, width, yerr=lar_sd_ep5, capsize=4, label='Laravel', color=color_lar, edgecolor='black', linewidth=0.6)
    ax2.bar(x + width/2, nest_rps_ep5, width, yerr=nest_sd_ep5, capsize=4, label='NestJS', color=color_nest, edgecolor='black', linewidth=0.6)

    ax2.set_title('(b) EP5: In-Place Update (PATCH)')
    ax2.set_xlabel('Concurrency Level (Virtual Users)')
    ax2.set_ylabel('Throughput (req/s)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(['1 VU', '2 VU', '4 VU*', '10 VU*'])
    ax2.set_ylim(0, 3000)

    fig.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, 'fig1_s1_throughput.png')
    svg_path = os.path.join(OUTPUT_DIR, 'fig1_s1_throughput.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")

def plot_latency(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.4), sharey=True)
    vu_levels = [1, 2, 4, 10]
    x = np.arange(len(vu_levels))
    width = 0.35

    color_lar = '#d9534f'
    color_nest = '#2b6cb0'

    # EP1 Latency
    lar_p95_ep1 = [data[('EP1', u, 'laravel')]['p95'] for u in vu_levels]
    lar_sd_ep1 = [data[('EP1', u, 'laravel')]['p95_sd'] for u in vu_levels]
    nest_p95_ep1 = [data[('EP1', u, 'nestjs')]['p95'] for u in vu_levels]
    nest_sd_ep1 = [data[('EP1', u, 'nestjs')]['p95_sd'] for u in vu_levels]

    ax1.bar(x - width/2, lar_p95_ep1, width, yerr=lar_sd_ep1, capsize=4, label='Laravel', color=color_lar, edgecolor='black', linewidth=0.6)
    ax1.bar(x + width/2, nest_p95_ep1, width, yerr=nest_sd_ep1, capsize=4, label='NestJS', color=color_nest, edgecolor='black', linewidth=0.6)

    ax1.set_title('(a) EP1: Single-Table Read (GET)')
    ax1.set_xlabel('Concurrency Level (Virtual Users)')
    ax1.set_ylabel('Tail Latency $p_{95}$ (ms)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(['1 VU', '2 VU', '4 VU*', '10 VU*'])
    ax1.legend(loc='upper left', frameon=True)
    ax1.set_ylim(0, 26)

    for i in range(len(vu_levels)):
        ax1.text(i - width/2, lar_p95_ep1[i] + lar_sd_ep1[i] + 0.6, f"{lar_p95_ep1[i]:.0f}", ha='center', fontsize=8)
        ax1.text(i + width/2, nest_p95_ep1[i] + nest_sd_ep1[i] + 0.6, f"{nest_p95_ep1[i]:.0f}", ha='center', fontsize=8, color=color_nest)

    # EP5 Latency
    lar_p95_ep5 = [data[('EP5', u, 'laravel')]['p95'] for u in vu_levels]
    lar_sd_ep5 = [data[('EP5', u, 'laravel')]['p95_sd'] for u in vu_levels]
    nest_p95_ep5 = [data[('EP5', u, 'nestjs')]['p95'] for u in vu_levels]
    nest_sd_ep5 = [data[('EP5', u, 'nestjs')]['p95_sd'] for u in vu_levels]

    ax2.bar(x - width/2, lar_p95_ep5, width, yerr=lar_sd_ep5, capsize=4, label='Laravel', color=color_lar, edgecolor='black', linewidth=0.6)
    ax2.bar(x + width/2, nest_p95_ep5, width, yerr=nest_sd_ep5, capsize=4, label='NestJS', color=color_nest, edgecolor='black', linewidth=0.6)

    ax2.set_title('(b) EP5: In-Place Update (PATCH)')
    ax2.set_xlabel('Concurrency Level (Virtual Users)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(['1 VU', '2 VU', '4 VU*', '10 VU*'])
    ax2.set_ylim(0, 26)

    for i in range(len(vu_levels)):
        ax2.text(i - width/2, lar_p95_ep5[i] + lar_sd_ep5[i] + 0.6, f"{lar_p95_ep5[i]:.0f}", ha='center', fontsize=8)
        ax2.text(i + width/2, nest_p95_ep5[i] + nest_sd_ep5[i] + 0.6, f"{nest_p95_ep5[i]:.0f}", ha='center', fontsize=8, color=color_nest)

    fig.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, 'fig2_s1_latency.png')
    svg_path = os.path.join(OUTPUT_DIR, 'fig2_s1_latency.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")

def plot_resources(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.4))
    endpoints = ['EP1 (Read)', 'EP5 (Update)']
    ep_keys = ['EP1', 'EP5']
    x = np.arange(len(endpoints))
    width = 0.35

    color_lar = '#d9534f'
    color_nest = '#2b6cb0'

    # Panel 1: CPU Time per Request (at 1 VU baseline)
    cpu_lar = [data[('EP1', 1, 'laravel')]['cpu_req'], data[('EP5', 1, 'laravel')]['cpu_req']]
    cpu_nest = [data[('EP1', 1, 'nestjs')]['cpu_req'], data[('EP5', 1, 'nestjs')]['cpu_req']]
    cpu_lar_sd = [data[('EP1', 1, 'laravel')]['cpu_req_sd'], data[('EP5', 1, 'laravel')]['cpu_req_sd']]
    cpu_nest_sd = [data[('EP1', 1, 'nestjs')]['cpu_req_sd'], data[('EP5', 1, 'nestjs')]['cpu_req_sd']]

    ax1.bar(x - width/2, cpu_lar, width, yerr=cpu_lar_sd, capsize=4, label='Laravel', color=color_lar, edgecolor='black', linewidth=0.6)
    ax1.bar(x + width/2, cpu_nest, width, yerr=cpu_nest_sd, capsize=4, label='NestJS', color=color_nest, edgecolor='black', linewidth=0.6)
    ax1.set_title('(a) Compute Cost: CPU per Request (1 VU)')
    ax1.set_ylabel('Application CPU Time (ms / req)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(endpoints)
    ax1.set_ylim(0, 8.0)
    ax1.legend(loc='upper right', frameon=True)

    for i in range(len(ep_keys)):
        ax1.text(i - width/2, cpu_lar[i] + cpu_lar_sd[i] + 0.25, f"{cpu_lar[i]:.2f}", ha='center', fontsize=8)
        ax1.text(i + width/2, cpu_nest[i] + cpu_nest_sd[i] + 0.25, f"{cpu_nest[i]:.2f}", ha='center', fontsize=8, color=color_nest)

    # Panel 2: Memory Footprint (Peak RAM in MiB at 1 VU) - pure bars without misleading tiny error whiskers
    mem_lar = [data[('EP1', 1, 'laravel')]['mem_pk'], data[('EP5', 1, 'laravel')]['mem_pk']]
    mem_nest = [data[('EP1', 1, 'nestjs')]['mem_pk'], data[('EP5', 1, 'nestjs')]['mem_pk']]

    ax2.bar(x - width/2, mem_lar, width, label='Laravel', color=color_lar, edgecolor='black', linewidth=0.6)
    ax2.bar(x + width/2, nest_mem := mem_nest, width, label='NestJS', color=color_nest, edgecolor='black', linewidth=0.6)
    ax2.set_title('(b) Memory Footprint: Peak RAM (1 VU)')
    ax2.set_ylabel('Peak Memory Usage (MiB)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(endpoints)
    ax2.set_ylim(0, 850)

    for i in range(len(ep_keys)):
        ax2.text(i - width/2, mem_lar[i] + 25, f"{mem_lar[i]:.1f}", ha='center', fontsize=8)
        ax2.text(i + width/2, mem_nest[i] + 25, f"{mem_nest[i]:.1f}", ha='center', fontsize=8, color=color_nest)

    fig.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, 'fig3_s1_resources.png')
    svg_path = os.path.join(OUTPUT_DIR, 'fig3_s1_resources.svg')
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)
    plt.close(fig)
    print(f"Generated: {png_path} & {svg_path}")

if __name__ == '__main__':
    data = load_summary()
    plot_throughput(data)
    plot_latency(data)
    plot_resources(data)
