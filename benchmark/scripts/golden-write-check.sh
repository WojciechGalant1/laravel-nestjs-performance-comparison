#!/usr/bin/env bash
# Execute one deterministic write request for EP7, EP8 and EP9.
# The output excludes generated ids and timestamps so two framework runs can
# be compared after resetting their databases from the same template.
set -euo pipefail

cd "$(dirname "$0")/.."
framework="${1:-}"
case "$framework" in
    laravel) nginx=laravel-nginx; db=laravel_app ;;
    nestjs) nginx=nestjs-nginx; db=nestjs_app ;;
    *) echo "Usage: $0 <laravel|nestjs>" >&2; exit 1 ;;
esac

login=$(docker compose exec -T "$nginx" curl -fsS \
    -H 'Accept: application/json' -H 'Content-Type: application/json' \
    -d '{"email":"manager@example.com","password":"password"}' \
    http://localhost/api/auth/login)
token=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["access_token"])' "$login")
auth=(-H "Authorization: Bearer ${token}" -H 'Accept: application/json')
request() {
    docker compose exec -T "$nginx" curl -fsS -H 'Content-Type: application/json' \
        "${auth[@]}" -X "$1" -d "$3" "http://localhost$2"
}
psql() {
    docker compose exec -T postgres psql -U postgres -d "$db" -v ON_ERROR_STOP=1 -X -q -A -t "$@"
}

psql -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;" >/dev/null
psql -c "SELECT pg_stat_statements_reset();" >/dev/null

request POST /api/orders '{"table_id":1,"items":[{"menu_item_id":1,"quantity":1}]}' >/dev/null
request PATCH /api/orders/1/status '{"status":"paid"}' >/dev/null
request POST /api/reservations \
    '{"table_id":1,"customer_name":"Golden Guest","phone_number":"+48000000002","reservation_date":"2099-01-02","reservation_time":"12:00","party_size":2,"duration_minutes":30}' >/dev/null

echo "framework=${framework}"
echo "EP7.order=$(psql -c "SELECT json_build_object('table_id', table_id, 'user_id', user_id, 'total_price', total_price::text, 'status', status::text) FROM orders ORDER BY id DESC LIMIT 1;")"
echo "EP7.item=$(psql -c "SELECT json_build_object('menu_item_id', menu_item_id, 'quantity', quantity, 'unit_price', unit_price::text, 'notes', notes, 'status', status::text) FROM order_items ORDER BY id DESC LIMIT 1;")"
echo "EP8.order=$(psql -c "SELECT json_build_object('table_id', table_id, 'user_id', user_id, 'total_price', total_price::text, 'status', status::text) FROM orders WHERE id = 1;")"
echo "EP9.reservation=$(psql -c "SELECT json_build_object('table_id', table_id, 'customer_name', customer_name, 'phone_number', phone_number, 'reservation_date', reservation_date, 'reservation_time', reservation_time, 'party_size', party_size, 'duration_minutes', duration_minutes, 'status', status::text, 'notes', notes) FROM reservations WHERE customer_name = 'Golden Guest' ORDER BY id DESC LIMIT 1;")"
