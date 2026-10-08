#!/usr/bin/env bash
# One instrumented request per S3 endpoint, outside the load run.
# The X-Debug-Queries header turns on the query counter (X-Query-Count and the
# SQL log). JMeter plans omit the header, so this cost never enters the measurement.
#
# Usage: scripts/query-count.sh <laravel|nestjs>
# The chosen stack must already be running. Writes results/s3/query-count-<framework>.txt
set -euo pipefail

cd "$(dirname "$0")/.."

framework="${1:-}"
case "$framework" in
    laravel) nginx=laravel-nginx ;;
    nestjs) nginx=nestjs-nginx ;;
    *) echo "Usage: $0 <laravel|nestjs>" >&2; exit 1 ;;
esac

if [ -z "$(docker compose ps -q --status running "$nginx")" ]; then
    echo "${nginx} is not running" >&2
    exit 1
fi

login=$(docker compose exec -T "$nginx" curl -fsS \
    -H 'Accept: application/json' -H 'Content-Type: application/json' \
    -d '{"email":"manager@example.com","password":"password"}' \
    http://localhost/api/auth/login)
token=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["access_token"])' "$login")

mkdir -p results/s3
out="results/s3/query-count-${framework}.txt"
: >"$out"

for spec in "EP1 /api/tables?page=1" "EP2 /api/menu-items?page=1" "EP4 /api/orders/1" "EP5 /api/dishes/1/ingredients" "EP6 /api/dashboard/summary"; do
    label=${spec%% *}
    path=${spec#* }
    headers=$(docker compose exec -T "$nginx" curl -sS -D - -o /dev/null \
        -H "Authorization: Bearer ${token}" \
        -H 'Accept: application/json' \
        -H 'X-Debug-Queries: 1' \
        "http://localhost${path}")
    code=$(printf '%s\n' "$headers" | awk 'toupper($1) ~ /^HTTP/ { code=$2 } END { print code }')
    count=$(printf '%s\n' "$headers" | awk 'tolower($1) ~ /^x-query-count:/ { print $2 }' | tr -d '\r')
    if [ -z "$count" ]; then
        count="missing"
    fi
    echo "${label} ${path} http=${code} queries=${count}" | tee -a "$out"
done

echo "Wrote ${out}"
