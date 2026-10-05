#!/usr/bin/env bash
# Run one measurement scenario as described in metodyka.md (Sections 3.3 and 3.6).
# For every endpoint x concurrency level x repetition:
#   1. scripts/db-reset.sh: restore the database from its template, restart the app
#   2. warm-up run (results retained only for integrity checks)
#   3. docker stats streamed to stats.csv for the duration of the measurement
#   4. measurement run, written to results.jtl
#   5. meta.json with the parameters and the effective container limits
#
# Usage:
#   scripts/run-scenario.sh <laravel|nestjs> <scenario>   one stack (control / resume)
#   scripts/run-scenario.sh both <scenario>               both stacks, interleaved
#
# Interleaved mode puts the repetition in the outer loop and the framework in the
# inner loop. The order of the two frameworks within each repetition is shuffled
# from INTERLEAVE_SEED (default 20261002) so the comparison is not confounded with
# thermal or host drift. Only one application stack runs at a time.
#
# Environment (defaults follow the methodology):
#   MODE=isolated|mixed
#   ENDPOINTS / USERS override the scenario defaults
#   REPS=10 WARMUP=120 DURATION=180 RAMPUP=10
#   S1 defaults: ENDPOINTS="EP1 EP2 EP8" USERS="1 2 4 10"
#   S2 defaults: ENDPOINTS="EP3 EP7" USERS="200 500 1000"
#   S3 defaults: ENDPOINTS="EP1 EP4 EP5 EP6" USERS="1 2 4 10"
#   DB_POOL_SIZE=1   NestJS control run; results go to results/s2-pool1/
#   INTERLEAVE_SEED  integer used only in `both` mode
#
# Output: results/<scenario>/<framework>/<endpoint>/vu<N>/rep<NN>/
#   results.jtl, jmeter.log, warmup.log, stats.csv, meta.json
#
# Completed repetitions (meta.json with "status": "complete") are skipped, so an
# interrupted series can be resumed by running the same command again.
set -euo pipefail

cd "$(dirname "$0")/.."

usage() { echo "Usage: $0 <laravel|nestjs|both> <scenario>" >&2; exit 1; }
[ $# -eq 2 ] || usage
target="$1" scenario="$2"

case "$target" in
    laravel|nestjs) frameworks=("$target") ;;
    both) frameworks=(laravel nestjs) ;;
    *) usage ;;
esac

case "$scenario" in
    s1) default_endpoints="EP1 EP2 EP8"; extra_endpoints="PING"; default_users="1 2 4 10" ;;
    s2) default_endpoints="EP3 EP7"; extra_endpoints=""; default_users="200 500 1000" ;;
    s3) default_endpoints="EP1 EP4 EP5 EP6"; extra_endpoints=""; default_users="1 2 4 10" ;;
    *) echo "Unknown scenario: ${scenario} (no jmeter/${scenario}.jmx defaults)" >&2; exit 1 ;;
esac

MODE="${MODE:-isolated}"
ENDPOINTS="${ENDPOINTS:-$default_endpoints}"
USERS="${USERS:-$default_users}"
REPS="${REPS:-10}"
WARMUP="${WARMUP:-120}"
DURATION="${DURATION:-180}"
RAMPUP="${RAMPUP:-10}"
INTERLEAVE_SEED="${INTERLEAVE_SEED:-20261002}"

case "$MODE" in
    isolated)
        for ep in $ENDPOINTS; do
            [[ " $default_endpoints $extra_endpoints " == *" $ep "* ]] || { echo "Endpoint ${ep} is not part of ${scenario}" >&2; exit 1; }
        done
        read -r -a endpoints <<<"$ENDPOINTS"
        ;;
    mixed) endpoints=(MIXED) ;;
    *) echo "MODE must be isolated or mixed" >&2; exit 1 ;;
esac
read -r -a users <<<"$USERS"

[ -f "jmeter/${scenario}.jmx" ] || { echo "Missing jmeter/${scenario}.jmx" >&2; exit 1; }
[ -f jmeter/data/ranges.properties ] || { echo "Missing jmeter/data/ranges.properties; run scripts/jmeter-data.sh" >&2; exit 1; }

running() { [ -n "$(docker compose ps -q --status running "$1")" ]; }

stack_for() {
    case "$1" in
        laravel) echo laravel-app laravel-nginx nestjs-app nestjs-nginx ;;
        nestjs) echo nestjs-app nestjs-nginx laravel-app laravel-nginx ;;
    esac
}

ensure_stack() {
    local fw="$1"
    read -r app nginx other other_nginx <<<"$(stack_for "$fw")"
    if running "$other" || running "$other_nginx"; then
        echo "Stopping ${other} ${other_nginx} so only ${fw} uses the CPUs"
        docker compose stop "$other" "$other_nginx" >/dev/null
    fi
    running postgres || { echo "postgres is not running: docker compose up -d --wait postgres" >&2; exit 1; }
    if ! running "$app" || ! running "$nginx"; then
        docker compose --profile "$fw" up -d --wait "$app" "$nginx" >/dev/null
    fi
}

align_nestjs_pool() {
    local desired_pool="${DB_POOL_SIZE:-10}"
    running nestjs-app || return 0
    local actual_pool
    actual_pool=$(docker compose exec -T nestjs-app printenv DB_POOL_SIZE)
    if [ "$actual_pool" != "$desired_pool" ]; then
        echo "Recreating nestjs-app with DB_POOL_SIZE=${desired_pool} (container has ${actual_pool})"
        DB_POOL_SIZE="$desired_pool" docker compose --profile nestjs up -d --force-recreate --no-deps nestjs-app >/dev/null
        actual_pool=$(docker compose exec -T nestjs-app printenv DB_POOL_SIZE)
        if [ "$actual_pool" != "$desired_pool" ]; then
            echo "nestjs-app still has DB_POOL_SIZE=${actual_pool}, expected ${desired_pool}" >&2
            exit 1
        fi
    fi
}

docker compose --profile loadtest build -q jmeter

desired_pool="${DB_POOL_SIZE:-10}"
out_name="${OUT_NAME:-$scenario}"
if [ -z "${OUT_NAME:-}" ] && [ "$scenario" = s2 ] && [ "$desired_pool" != 10 ]; then
    out_name="s2-pool${desired_pool}"
fi

jmeter() {
    local name=()
    if [ "${1:-}" = "--name" ]; then
        name=(--name "$2")
        shift 2
    fi
    docker compose --profile loadtest run --rm -T --no-deps "${name[@]}" jmeter \
        -n -t "/tests/${scenario}.jmx" \
        -q /tests/run.properties -q /tests/data/ranges.properties \
        -Jhost="$nginx" -Jport=80 -Jrampup="$RAMPUP" "$@"
}

# docker stats ignores SIGTERM and SIGINT when started in the background, so it is
# stopped with SIGKILL (it only reads statistics). Every refresh is prefixed with
# terminal control sequences, which are stripped; each line gets a timestamp from
# the same clock as the measurement window in meta.json.
start_stats() {
    local out="$1"
    local jmeter_id="${2:-}"
    local ids
    ids=$(docker compose ps -q "$app" "$nginx" postgres | tr '\n' ' ')
    if [ -n "$jmeter_id" ]; then
        ids="$ids $jmeter_id"
    fi
    echo "epoch,name,cpu_perc,mem_usage,mem_limit,mem_perc" >"$out"
    # shellcheck disable=SC2086
    docker stats --format '{{json .}}' $ids > >(
        re='"CPUPerc":"([0-9.]+)%".*"MemPerc":"([0-9.]+)%","MemUsage":"([^ ]+) / ([^"]+)","Name":"([^"]+)"'
        while IFS= read -r line; do
            line="${line//$'\e[H'/}"
            line="${line//$'\e[J'/}"
            line="${line//$'\e[K'/}"
            if [[ $line =~ $re ]]; then
                printf '%s,%s,%s,%s,%s,%s\n' "$EPOCHREALTIME" "${BASH_REMATCH[5]}" \
                    "${BASH_REMATCH[1]}" "${BASH_REMATCH[3]}" "${BASH_REMATCH[4]}" "${BASH_REMATCH[2]}"
            fi
        done >>"$out"
    ) &
    STATS_PID=$!
}

stop_stats() {
    kill -KILL "$STATS_PID" 2>/dev/null || true
    wait "$STATS_PID" 2>/dev/null || true
    sleep 0.5
}

inspect() { docker inspect -f "$1" "$(docker compose ps -q "$app")"; }

clock_offset() {
    local t0 vm t1
    t0="$EPOCHREALTIME"
    vm=$(docker compose exec -T postgres date +%s.%N)
    t1="$EPOCHREALTIME"
    awk -v a="$t0" -v b="$t1" -v v="$vm" 'BEGIN { printf "%.3f", v - (a + b) / 2 }'
}

row_counts() {
    local db="$1"
    docker compose exec -T postgres sh -c \
        'psql -U "$POSTGRES_USER" -d '"$db"' -v ON_ERROR_STOP=1 -X -q -A -t' <<'SQL'
SELECT json_build_object(
  'orders', (SELECT count(*)::bigint FROM orders),
  'order_items', (SELECT count(*)::bigint FROM order_items),
  'reservations', (SELECT count(*)::bigint FROM reservations)
);
SQL
}

framework_order() {
    local rep="$1"
    python3 -c '
import random, sys
seed, rep = int(sys.argv[1]), int(sys.argv[2])
rng = random.Random((seed, rep))
xs = ["laravel", "nestjs"]
rng.shuffle(xs)
print(" ".join(xs))
' "$INTERLEAVE_SEED" "$rep"
}

total=$(( ${#endpoints[@]} * ${#users[@]} * REPS * ${#frameworks[@]} ))
per_run=$(( WARMUP + DURATION + 30 ))
done_runs=0

run_one() {
    local framework="$1" ep="$2" vu="$3" rep="$4" order="$5"
    read -r app nginx other other_nginx <<<"$(stack_for "$framework")"
    ensure_stack "$framework"
    [ "$framework" = nestjs ] && align_nestjs_pool

    local pool_size="n/a"
    [ "$framework" = nestjs ] && pool_size=$(docker compose exec -T nestjs-app printenv DB_POOL_SIZE)
    local app_cpus app_mem_mib image postgres_cpus
    local git_commit laravel_tree nestjs_tree
    git_commit=$(git rev-parse HEAD)
    laravel_tree=$(git rev-parse HEAD:benchmark/apps/laravel-app)
    nestjs_tree=$(git rev-parse HEAD:benchmark/apps/nestjs-app)
    app_cpus=$(awk -v n="$(inspect '{{.HostConfig.NanoCpus}}')" 'BEGIN { print n / 1e9 }')
    app_mem_mib=$(( $(inspect '{{.HostConfig.Memory}}') / 1024 / 1024 ))
    image=$(inspect '{{.Image}}')
    postgres_cpus=$(awk -v n="$(docker inspect -f '{{.HostConfig.NanoCpus}}' "$(docker compose ps -q postgres)")" \
        'BEGIN { c = n / 1e9; print (c > 0 ? c : 4) }')

    local rel dir container_dir
    rel="${out_name}/${framework}/${ep}/vu${vu}/rep$(printf '%02d' "$rep")"
    dir="results/${rel}"
    container_dir="/results/${rel}"
    done_runs=$((done_runs + 1))

    if grep -qs '"status": "complete"' "${dir}/meta.json"; then
        if ! grep -q "\"warmup_s\": ${WARMUP}," "${dir}/meta.json" \
            || ! grep -q "\"duration_s\": ${DURATION}," "${dir}/meta.json" \
            || ! grep -q "\"rampup_s\": ${RAMPUP}," "${dir}/meta.json" \
            || ! grep -q "\"db_pool_size\": \"${pool_size}\"," "${dir}/meta.json" \
            || ! grep -q "\"git_commit\": \"${git_commit}\"," "${dir}/meta.json" \
            || ! grep -q "\"${framework}_app_tree\": \"$( [ "$framework" = laravel ] && printf '%s' "$laravel_tree" || printf '%s' "$nestjs_tree" )\"," "${dir}/meta.json"; then
            echo "${dir} holds a run with different parameters or source revision; move it away first." >&2
            exit 1
        fi
        echo "[${done_runs}/${total}] ${dir}: already complete, skipped"
        return 0
    fi
    rm -rf "$dir" && mkdir -p "$dir"

    local eta=$(( (total - done_runs + 1) * per_run / 60 ))
    echo "[${done_runs}/${total}] ${framework} ${out_name} ${ep} vu=${vu} rep=${rep} (about ${eta} min left)"

    scripts/db-reset.sh "$framework" >/dev/null
    db="${framework}_app"
    local baseline_counts warmup_successes measurement_successes expected_orders expected_items expected_reservations
    baseline_counts=$(row_counts "$db" | tr -d '\r\n ')

    jmeter -Jendpoint="$ep" -Jusers="$vu" -Jduration="$WARMUP" \
        -l "${container_dir}/warmup.jtl" -j "${container_dir}/warmup.log" >/dev/null

    local offset started finished status measure_name mpid jid db counts
    offset=$(clock_offset)
    started="$EPOCHREALTIME"
    status=complete
    measure_name="benchmark-jmeter-measure"
    docker rm -f "$measure_name" >/dev/null 2>&1 || true
    jmeter --name "$measure_name" -Jendpoint="$ep" -Jusers="$vu" -Jduration="$DURATION" \
        -l "${container_dir}/results.jtl" -j "${container_dir}/jmeter.log" >/dev/null &
    mpid=$!
    jid=""
    for _ in $(seq 1 100); do
        jid=$(docker ps -q -f "name=^/${measure_name}$")
        [ -n "$jid" ] && break
        kill -0 "$mpid" 2>/dev/null || break
        sleep 0.1
    done
    start_stats "${dir}/stats.csv" "$jid"
    wait "$mpid" || status=failed
    finished="$EPOCHREALTIME"
    stop_stats

    if ! grep -q ',SETUP_login,200,' "${dir}/results.jtl" 2>/dev/null \
        || ! grep -q ',SETUP_login,200,' "${dir}/warmup.jtl" 2>/dev/null; then
        status=failed
    fi

    counts=$(row_counts "$db" | tr -d '\r\n ')

    warmup_successes=$(awk -F, -v ep="$ep" '$3 == ep && $4 == 201 { n++ } END { print n + 0 }' \
        "${dir}/warmup.jtl")
    measurement_successes=$(awk -F, -v ep="$ep" '$3 == ep && $4 == 201 { n++ } END { print n + 0 }' \
        "${dir}/results.jtl")
    expected_orders=0
    expected_items=0
    expected_reservations=0
    if [ "$ep" = EP7 ]; then
        expected_orders=$((warmup_successes + measurement_successes))
        expected_items="$expected_orders"
    fi

    json_count() {
        printf '%s\n' "$1" | sed -n "s/.*\"$2\":\([0-9][0-9]*\).*/\1/p"
    }
    baseline_orders=$(json_count "$baseline_counts" orders)
    final_orders=$(json_count "$counts" orders)
    baseline_items=$(json_count "$baseline_counts" order_items)
    final_items=$(json_count "$counts" order_items)
    baseline_reservations=$(json_count "$baseline_counts" reservations)
    final_reservations=$(json_count "$counts" reservations)
    integrity=pass
    [ $((final_orders - baseline_orders)) -eq "$expected_orders" ] || integrity=fail
    [ $((final_items - baseline_items)) -eq "$expected_items" ] || integrity=fail
    [ $((final_reservations - baseline_reservations)) -eq "$expected_reservations" ] || integrity=fail
    if [ "$integrity" != pass ]; then
        status=failed
        echo "Integrity gate failed for ${dir}: baseline=${baseline_counts} final=${counts} " \
            "expected201=${warmup_successes}+${measurement_successes}" >&2
    fi

    cat >"${dir}/meta.json" <<EOF
{
  "status": "${status}",
  "framework": "${framework}",
  "scenario": "${scenario}",
  "endpoint": "${ep}",
  "mode": "${MODE}",
  "users": ${vu},
  "repetition": ${rep},
  "rampup_s": ${RAMPUP},
  "warmup_s": ${WARMUP},
  "duration_s": ${DURATION},
  "measurement_started": ${started},
  "measurement_finished": ${finished},
  "clock_offset_s": ${offset},
  "app_cpus": ${app_cpus},
  "postgres_cpus": ${postgres_cpus},
  "app_memory_mib": ${app_mem_mib},
  "db_pool_size": "${pool_size}",
  "app_image": "${image}",
  "interleave_seed": ${INTERLEAVE_SEED},
  "framework_order": "${order}",
  "git_commit": "${git_commit}",
  "laravel_app_tree": "${laravel_tree}",
  "nestjs_app_tree": "${nestjs_tree}",
  "integrity_gate": "${integrity}",
  "warmup_201": ${warmup_successes},
  "measurement_201": ${measurement_successes},
  "expected_order_rows": ${expected_orders},
  "expected_order_item_rows": ${expected_items},
  "expected_reservation_rows": ${expected_reservations},
  "baseline_row_counts": ${baseline_counts:-null},
  "row_counts": ${counts:-null}
}
EOF
    if [ "$status" != complete ]; then
        echo "Run failed, see ${dir}/jmeter.log and ${dir}/results.jtl" >&2
        exit 1
    fi
}

# Single-stack mode still requires the stack to be up before the first run.
if [ "$target" != both ]; then
    read -r app nginx other other_nginx <<<"$(stack_for "$target")"
    for svc in "$app" "$nginx" postgres; do
        running "$svc" || { echo "${svc} is not running: docker compose --profile ${target} up -d --wait" >&2; exit 1; }
    done
    if running "$other"; then
        echo "${other} is running as well; both stacks would share the same CPUs." >&2
        echo "Stop it first: docker compose stop ${other} ${other_nginx}" >&2
        exit 1
    fi
    [ "$target" = nestjs ] && align_nestjs_pool
else
    running postgres || { echo "postgres is not running: docker compose up -d --wait postgres" >&2; exit 1; }
fi

for rep in $(seq 1 "$REPS"); do
    if [ "$target" = both ]; then
        order=$(framework_order "$rep")
    else
        order="$target"
    fi
    for ep in "${endpoints[@]}"; do
        for vu in "${users[@]}"; do
            for framework in $order; do
                case " ${frameworks[*]} " in
                    *" $framework "*) ;;
                    *) continue ;;
                esac
                run_one "$framework" "$ep" "$vu" "$rep" "$order"
            done
        done
    done
done

echo "Done: results/${out_name}/"
