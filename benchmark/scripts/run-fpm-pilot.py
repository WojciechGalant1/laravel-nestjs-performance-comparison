#!/usr/bin/env python3
"""Run a pilot benchmark across various pm.max_children values for Laravel on Scenario S2 (EP3, EP7) at 500 & 1000 VU."""

import os
import sys
import subprocess
import json
import csv
from pathlib import Path

# Add benchmark/scripts to path to import summarize_data
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from summarize_data import summarise_run

ROOT = SCRIPT_DIR.parent
WORKERS_LIST = [4, 8, 16, 24, 32, 40]
VU_LEVELS = [500, 1000]
ENDPOINTS = ["EP3", "EP7"]
WARMUP = 30
DURATION = 30
RAMPUP = 10

PILOT_DIR = ROOT / "results" / "smoke" / "s2-fpm-pilot"
SUMMARY_CSV = PILOT_DIR / "summary.csv"

def run_cmd(cmd, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    res = subprocess.run(cmd, cwd=str(ROOT), env=merged_env, shell=True)
    if res.returncode != 0:
        print(f"Error running command: {cmd}", file=sys.stderr)
        return False
    return True

def main():
    PILOT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Ensure nestjs containers are stopped so they do not share CPUs
    run_cmd("docker compose stop nestjs-app nestjs-nginx >/dev/null 2>&1 || true")

    all_results = []
    
    total_runs = len(WORKERS_LIST) * len(VU_LEVELS) * len(ENDPOINTS)
    run_idx = 0

    print(f"Starting Laravel FPM Pilot: {total_runs} runs total (Warmup={WARMUP}s, Duration={DURATION}s)")
    print(f"Workers: {WORKERS_LIST} | VU: {VU_LEVELS} | Endpoints: {ENDPOINTS}")
    print("-" * 80)

    for w in WORKERS_LIST:
        out_name = f"smoke/s2-fpm-pilot/workers{w}"
        for ep in ENDPOINTS:
            for vu in VU_LEVELS:
                run_idx += 1
                run_dir = ROOT / "results" / out_name / "laravel" / ep / f"vu{vu}" / "rep01"
                
                print(f"[{run_idx}/{total_runs}] Testing Workers={w}, Endpoint={ep}, VU={vu}...")
                
                cmd = (
                    f'PM_MAX_CHILDREN="{w}" '
                    f'OUT_NAME="{out_name}" '
                    f'ENDPOINTS="{ep}" '
                    f'USERS="{vu}" '
                    f'REPS=1 '
                    f'WARMUP="{WARMUP}" '
                    f'DURATION="{DURATION}" '
                    f'RAMPUP="{RAMPUP}" '
                    f'./scripts/run-scenario.sh laravel s2'
                )
                
                success = run_cmd(cmd, env={"PM_MAX_CHILDREN": str(w)})
                if not success:
                    print(f"Failed run: Workers={w}, Endpoint={ep}, VU={vu}")
                    continue
                
                rows = summarise_run(run_dir)
                for r in rows:
                    r["workers"] = w
                    all_results.append(r)
                    
                    # Print immediate metric line
                    app_cpu = r.get("app_cpu_share_pct", 0) * 100
                    pg_cpu = r.get("postgres_cpu_share_pct", 0) * 100
                    print(f"    -> Done: Throughput={r['throughput_rps']:.1f} RPS | p95={r['p95_ms']:.1f} ms | "
                          f"App CPU={app_cpu:.1f}% | PG CPU={pg_cpu:.1f}% | Err={r['error_rate_pct']:.2f}%")

        # Save incremental CSV
        save_summary(all_results)
        print_summary_table(all_results)

def save_summary(results):
    if not results:
        return
    fieldnames = [
        "workers", "endpoint", "users", "throughput_rps", "p50_ms", "p95_ms", "mean_ms",
        "app_cpu_share_pct", "postgres_cpu_share_pct", "error_rate_pct", "samples"
    ]
    with SUMMARY_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)

def print_summary_table(results):
    if not results:
        return
    print("\n" + "=" * 80)
    print("CURRENT PILOT SUMMARY TABLE (Laravel pm.max_children sensitivity)")
    print("=" * 80)
    header = f"{'Workers':<8} | {'Endpoint':<8} | {'VU':<6} | {'Throughput':<12} | {'p95 (ms)':<10} | {'App CPU %':<10} | {'PG CPU %':<10}"
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda x: (x.get("endpoint", ""), x.get("users", 0), x.get("workers", 0))):
        app_cpu = r.get("app_cpu_share_pct", 0) * 100
        pg_cpu = r.get("postgres_cpu_share_pct", 0) * 100
        print(f"{r['workers']:<8} | {r['endpoint']:<8} | {r['users']:<6} | {r['throughput_rps']:<12.1f} | {r['p95_ms']:<10.1f} | {app_cpu:<10.1f} | {pg_cpu:<10.1f}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
