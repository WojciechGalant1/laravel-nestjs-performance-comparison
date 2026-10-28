#!/usr/bin/env bash
# Run the complete symmetric sensitivity series (n=10) on Scenario S2 (EP3, 200, 500, 1000 VU):
# 1. NestJS with DB_POOL_SIZE=1 (4 total DB connections, matching Laravel's baseline 4 workers)
# 2. Laravel with PM_MAX_CHILDREN=8 (8 workers, optimal oversubscription sweet spot)
#
# Total runs: 30 (NestJS) + 30 (Laravel) = 60 runs (~4.2 hours).
# Safe to interrupt and resume: completed runs are automatically skipped.
set -euo pipefail

cd "$(dirname "$0")/.."

START_TIME=$(date +%s)
echo "=========================================================================="
echo " Starting S2 Sensitivity Series (n=10): EP3 @ 200, 500, 1000 VU"
echo " Started at: $(date)"
echo "=========================================================================="

# -------------------------------------------------------------------------
# Phase 1: NestJS DB_POOL_SIZE = 1 (4 connections)
# -------------------------------------------------------------------------
echo ""
echo ">>> [Phase 1/4] Running NestJS DB_POOL_SIZE=1 on EP3 (n=10)..."
DB_POOL_SIZE=1 \
OUT_NAME="s2-pool1" \
ENDPOINTS="EP3" \
USERS="200 500 1000" \
REPS=10 \
./scripts/run-scenario.sh nestjs s2

echo ""
echo ">>> [Phase 2/4] Summarizing NestJS s2-pool1 results..."
python3 scripts/summarize.py s2-pool1

# -------------------------------------------------------------------------
# Phase 3: Laravel PM_MAX_CHILDREN = 8 (8 workers)
# -------------------------------------------------------------------------
echo ""
echo ">>> [Phase 3/4] Running Laravel PM_MAX_CHILDREN=8 on EP3 (n=10)..."
PM_MAX_CHILDREN=8 \
OUT_NAME="s2-fpm8" \
ENDPOINTS="EP3" \
USERS="200 500 1000" \
REPS=10 \
./scripts/run-scenario.sh laravel s2

echo ""
echo ">>> [Phase 4/4] Summarizing Laravel s2-fpm8 results..."
python3 scripts/summarize.py s2-fpm8

# -------------------------------------------------------------------------
# Phase 5: Regenerate publication figures with full n=10 datasets
# -------------------------------------------------------------------------
echo ""
echo ">>> Regenerating S2 figures..."
if command -v python.exe >/dev/null 2>&1; then
    python.exe scripts/plot_s2.py
else
    python3 scripts/plot_s2.py || echo "Warning: matplotlib missing in linux python3, run plot_s2.py via python.exe"
fi

END_TIME=$(date +%s)
ELAPSED=$(( (END_TIME - START_TIME) / 60 ))
echo ""
echo "=========================================================================="
echo " S2 Sensitivity Series Finished in ${ELAPSED} minutes!"
echo " Finished at: $(date)"
echo " Results available in: results/s2-pool1/ and results/s2-fpm8/"
echo " Figures updated in: ../dokumenty/figures/fig2_s2_scalability_pool.png"
echo "=========================================================================="
