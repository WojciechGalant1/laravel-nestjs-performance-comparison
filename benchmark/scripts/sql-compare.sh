#!/usr/bin/env bash
# One-off: X-Query-Count plus all pg_stat_statements entries for EP2/EP1/EP3/EP4/EP5/EP6/EP7/EP8/EP9.
# Usage: scripts/sql-compare.sh <laravel|nestjs> [repeats]
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
    local path="$1" debug="${2:-}" method="${3:-GET}" body="${4:-}"
    local headers=(-H "Authorization: Bearer ${token}" -H 'Accept: application/json')
    local body_args=()
    if [ -n "$debug" ]; then
        headers+=(-H 'X-Debug-Queries: 1')
    fi
    if [ "$method" = POST ] || [ "$method" = PATCH ]; then
        headers+=(-H 'Content-Type: application/json')
        body_args=(-d "$body")
    fi
    docker compose exec -T "$nginx" curl -sS -D - -o /tmp/sql-compare-body \
        -X "$method" "${body_args[@]}" "${headers[@]}" "http://localhost${path}"
}

mkdir -p results/smoke
out="results/smoke/sql-compare-${framework}.txt"
{
    echo "# ${framework}  repeats=${repeats}  $(date -u +%FT%TZ)"
    echo
} >"$out"

# Warm workers and pools before the measured window.
for path in "/api/menu-items?page=1" "/api/tables?page=1" "/api/orders?page=1" "/api/orders/1" "/api/dishes/1/ingredients" "/api/dashboard/summary" "/api/orders/1/status" "/api/reservations"; do
    hit "$path" >/dev/null
done

for spec in \
    "EP2 /api/menu-items?page=1" \
    "EP1 /api/tables?page=1" \
    "EP3 /api/orders?page=1" \
    "EP4 /api/orders/1" \
    "EP5 /api/dishes/1/ingredients" \
    "EP6 /api/dashboard/summary" \
    "EP7 /api/orders" \
    "EP8 /api/orders/1/status" \
    "EP9 /api/reservations"
do
    label=${spec%% *}
    path=${spec#* }
    method=GET
    body=
    series_repeats="$repeats"
    if [ "$label" = EP7 ]; then
        method=POST
        body='{"table_id":1,"items":[{"menu_item_id":1,"quantity":1}]}'
    elif [ "$label" = EP8 ]; then
        method=PATCH
        body='{"status":"paid"}'
    elif [ "$label" = EP9 ]; then
        method=POST
        body='{"table_id":1,"customer_name":"SQL Compare","phone_number":"+48000000003","reservation_date":"2099-01-03","reservation_time":"12:00","party_size":2,"duration_minutes":30}'
        series_repeats=1
    fi

    headers=$(hit "$path" debug "$method" "$body")
    code=$(printf '%s\n' "$headers" | awk 'toupper($1) ~ /^HTTP/ { code=$2 } END { print code }')
    count=$(printf '%s\n' "$headers" | awk 'tolower($1) ~ /^x-query-count:/ { print $2 }' | tr -d '\r')
    [ -n "$count" ] || count="missing"

    # This reset is immediately before the measured request window.
    psql -c "SELECT pg_stat_statements_reset();" >/dev/null
    for _ in $(seq 1 "$series_repeats"); do
        hit "$path" "" "$method" "$body" >/dev/null
    done

    {
        echo "## ${label} ${method} ${path}  http=${code}  X-Query-Count=${count}"
        echo
        echo "### All tracked statements (including utility statements)"
        psql -c "SELECT calls, ROUND(total_exec_time::numeric, 3) AS total_ms, ROUND(mean_exec_time::numeric, 3) AS mean_ms, ROUND(total_exec_time::numeric / ${series_repeats}, 3) AS ms_per_req, query FROM pg_stat_statements WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database()) AND query NOT LIKE '%pg_stat_statements%' ORDER BY total_exec_time DESC;"
        echo
        echo "### Calls per request by statement class"
        psql -c "SELECT ROUND(SUM(calls)::numeric / ${series_repeats}, 3) AS calls_per_request, COUNT(*) AS tracked_statement_forms, COUNT(*) FILTER (WHERE query ~* '^(set|reset|deallocate|begin|start transaction|commit|rollback|prepare|execute)([[:space:]]|\$)') AS utility_statement_forms, ROUND(SUM(calls) FILTER (WHERE query ~* '^(set|reset|deallocate|begin|start transaction|commit|rollback|prepare|execute)([[:space:]]|\$)')::numeric / ${series_repeats}, 3) AS utility_calls_per_request FROM pg_stat_statements WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database()) AND query NOT LIKE '%pg_stat_statements%';"
        echo
    } >>"$out"

    echo "${label} http=${code} queries=${count}"
done

echo "Wrote ${out}"
