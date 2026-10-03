#!/usr/bin/env bash
# One-off: X-Query-Count plus pg_stat_statements for EP1/EP3/EP4/EP5.
# Usage: scripts/sql-compare.sh <laravel|nestjs> [repeats]
# The chosen stack must already be running. Writes results/smoke/sql-compare-<fw>.txt
set -euo pipefail

cd "$(dirname "$0")/.."

framework="${1:-}"
repeats="${2:-20}"
case "$framework" in
    laravel) nginx=laravel-nginx; db=laravel_app ;;
    nestjs) nginx=nestjs-nginx; db=nestjs_app ;;
    *) echo "Usage: $0 <laravel|nestjs> [repeats]" >&2; exit 1 ;;
esac

if [ -z "$(docker compose ps -q --status running "$nginx")" ]; then
    echo "${nginx} is not running" >&2
    exit 1
fi

psql() {
    docker compose exec -T postgres psql -U postgres -d "$db" -v ON_ERROR_STOP=1 -X -q -P pager=off "$@"
}

psql -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

login=$(docker compose exec -T "$nginx" curl -fsS \
    -H 'Accept: application/json' -H 'Content-Type: application/json' \
    -d '{"email":"manager@example.com","password":"password"}' \
    http://localhost/api/auth/login)
token=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["access_token"])' "$login")

hit() {
    local path="$1" debug="${2:-}"
    local headers=(-H "Authorization: Bearer ${token}" -H 'Accept: application/json')
    if [ -n "$debug" ]; then
        headers+=(-H 'X-Debug-Queries: 1')
    fi
    docker compose exec -T "$nginx" curl -sS -D - -o /tmp/sql-compare-body \
        "${headers[@]}" "http://localhost${path}"
}

mkdir -p results/smoke
out="results/smoke/sql-compare-${framework}.txt"
{
    echo "# ${framework}  repeats=${repeats}  $(date -u +%FT%TZ)"
    echo
} >"$out"

# Warm the workers / pools so PREPARE and JIT are not in the sample.
for path in "/api/tables?page=1" "/api/orders?page=1" "/api/orders/1" "/api/dishes/1/ingredients"; do
    hit "$path" >/dev/null
done

for spec in \
    "EP1 /api/tables?page=1" \
    "EP3 /api/orders?page=1" \
    "EP4 /api/orders/1" \
    "EP5 /api/dishes/1/ingredients"
do
    label=${spec%% *}
    path=${spec#* }

    headers=$(hit "$path" debug)
    code=$(printf '%s\n' "$headers" | awk 'toupper($1) ~ /^HTTP/ { code=$2 } END { print code }')
    count=$(printf '%s\n' "$headers" | awk 'tolower($1) ~ /^x-query-count:/ { print $2 }' | tr -d '\r')
    [ -n "$count" ] || count="missing"

    psql -c "SELECT pg_stat_statements_reset();" >/dev/null
    for _ in $(seq 1 "$repeats"); do
        hit "$path" >/dev/null
    done

    {
        echo "## ${label} ${path}  http=${code}  X-Query-Count=${count}  (counted request used the debug header; timed series did not)"
        echo
        psql -c "SELECT calls, ROUND(total_exec_time::numeric, 3) AS total_ms, ROUND(mean_exec_time::numeric, 3) AS mean_ms, ROUND(total_exec_time::numeric / ${repeats}, 3) AS ms_per_req, query FROM pg_stat_statements WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database()) AND query NOT LIKE '%pg_stat_statements%' ORDER BY total_exec_time DESC;"
        echo
    } >>"$out"

    echo "${label} http=${code} queries=${count}"
done

echo "Wrote ${out}"
