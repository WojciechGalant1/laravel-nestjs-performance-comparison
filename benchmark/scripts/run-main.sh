#!/usr/bin/env bash
# run-main.sh - Orchestrate the complete main benchmark measurement series (n=10)
#
# Usage:
#   scripts/run-main.sh [s1|s2|s2-pool1|s3|all]
#
# Defaults to "all" if no argument is provided.
# Output is saved to results/<scenario>/ and summarized with scripts/summarize.py.
# All runs are resumable; already completed repetitions are skipped.

set -euo pipefail
cd "$(dirname "$0")/.."

target="${1:-all}"

log_step() {
    echo ""
    echo "================================================================================"
    echo "  [$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "================================================================================"
    echo ""
}

run_s1() {
    log_step "Starting Main Series: Scenario S1 (Baseline CRUD, H1)"
    ./scripts/run-scenario.sh both s1
    log_step "Summarizing S1"
    python3 scripts/summarize.py s1
}

run_s2() {
    log_step "Starting Main Series: Scenario S2 (High Concurrency / Stress, H2)"
    ./scripts/run-scenario.sh both s2
    log_step "Summarizing S2"
    python3 scripts/summarize.py s2
}

run_s2_pool1() {
    log_step "Starting Main Series: Scenario S2 Control (NestJS DB_POOL_SIZE=1)"
    DB_POOL_SIZE=1 ./scripts/run-scenario.sh nestjs s2
    log_step "Summarizing S2 Control"
    python3 scripts/summarize.py s2-pool1
}

run_s3() {
    log_step "Starting Main Series: Scenario S3 (Relational Complexity, H3)"
    ./scripts/run-scenario.sh both s3
    log_step "Summarizing S3"
    python3 scripts/summarize.py s3
}

case "$target" in
    s1)
        run_s1
        ;;
    s2)
        run_s2
        ;;
    s2-pool1)
        run_s2_pool1
        ;;
    s3)
        run_s3
        ;;
    all)
        run_s1
        run_s2
        run_s2_pool1
        run_s3
        log_step "All main measurement series successfully completed!"
        ;;
    *)
        echo "Unknown target: $target. Valid options: s1, s2, s2-pool1, s3, all" >&2
        exit 1
        ;;
esac
