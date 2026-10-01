#!/usr/bin/env bash
# Run one measurement scenario against one framework, as described in metodyka.md
# (Sections 3.3 and 3.6). For every endpoint x concurrency level x repetition:
#   1. scripts/db-reset.sh: restore the database from its template, restart the app
#   2. warm-up run (results discarded)
#   3. docker stats streamed to stats.csv for the duration of the measurement
#   4. measurement run, written to results.jtl
#   5. meta.json with the parameters and the effective container limits
#
# Usage: scripts/run-scenario.sh <laravel|nestjs> <scenario>      e.g. ... nestjs s1
#
# Environment (defaults follow the methodology):
#   MODE=isolated|mixed   isolated: one run per endpoint; mixed: all endpoints in one run
#   ENDPOINTS="EP1 EP2 EP8" USERS="10 50" REPS=10 WARMUP=120 DURATION=180 RAMPUP=10
#   S2 defaults: ENDPOINTS="EP3 EP7 EP9" USERS="10 50 100 200 500 1000"
#   S3 defaults: ENDPOINTS="EP4 EP5 EP6" USERS="50 200"
#   DB_POOL_SIZE=1   NestJS control run; results go to results/s2-pool1/ instead of results/s2/
#
# Output: results/<scenario>/<framework>/<endpoint>/vu<N>/rep<NN>/
#   results.jtl, jmeter.log, warmup.log, stats.csv, meta.json
#
# Completed repetitions (meta.json with "status": "complete") are skipped, so an
# interrupted series can be resumed by running the same command again.
set -euo pipefail

cd "$(dirname "$0")/.."

usage() { echo "Usage: $0 <laravel|nestjs> <scenario>" >&2; exit 1; }
[ $# -eq 2 ] || usage
framework="$1" scenario="$2"

case "$framework" in
    laravel) app=laravel-app nginx=laravel-nginx other=nestjs-app ;;
    nestjs) app=nestjs-app nginx=nestjs-nginx other=laravel-app ;;
    *) usage ;;
esac

case "$scenario" in
    s1) default_endpoints="EP1 EP2 EP8"; default_users="10 50" ;;
    s2) default_endpoints="EP3 EP7 EP9"; default_users="10 50 100 200 500 1000" ;;
    s3) default_endpoints="EP4 EP5 EP6"; default_users="50 200" ;;
    *) echo "Unknown scenario: ${scenario} (no jmeter/${scenario}.jmx defaults)" >&2; exit 1 ;;
esac

MODE="${MODE:-isolated}"
ENDPOINTS="${ENDPOINTS:-$default_endpoints}"
USERS="${USERS:-$default_users}"
REPS="${REPS:-10}"
WARMUP="${WARMUP:-120}"
DURATION="${DURATION:-180}"
RAMPUP="${RAMPUP:-10}"

case "$MODE" in
    isolated)
        for ep in $ENDPOINTS; do
            [[ " $default_endpoints " == *" $ep "* ]] || { echo "Endpoint ${ep} is not part of ${scenario}" >&2; exit 1; }
        done
        read -r -a endpoints <<<"$ENDPOINTS"
        ;;
    # The plan's Switch Controller falls back to its first child for unknown names,
    # so the selector is validated here rather than in JMeter.
    mixed) endpoints=(MIXED) ;;
    *) echo "MODE must be isolated or mixed" >&2; exit 1 ;;
esac
read -r -a users <<<"$USERS"

[ -f "jmeter/${scenario}.jmx" ] || { echo "Missing jmeter/${scenario}.jmx" >&2; exit 1; }
[ -f jmeter/data/ranges.properties ] || { echo "Missing jmeter/data/ranges.properties; run scripts/jmeter-data.sh" >&2; exit 1; }

running() { [ -n "$(docker compose ps -q --status running "$1")" ]; }

for svc in "$app" "$nginx" postgres; do
    running "$svc" || { echo "${svc} is not running: docker compose --profile ${framework} up -d --wait" >&2; exit 1; }
done
if running "$other"; then
    echo "${other} is running as well; both stacks would share the same CPUs." >&2
    echo "Stop it first: docker compose stop ${other} ${other%-app}-nginx" >&2
    exit 1
fi

docker compose --profile loadtest build -q jmeter

# NestJS reads DB_POOL_SIZE at process start. Align the running container with the
# requested value (default 10) so a control run cannot leak into the next series.
# A non-default pool is written to its own directory: results/s2-pool<N>/.
desired_pool="${DB_POOL_SIZE:-10}"
out_name="$scenario"
if [ "$framework" = nestjs ]; then
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
    if [ "$scenario" = s2 ] && [ "$desired_pool" != 10 ]; then
        out_name="s2-pool${desired_pool}"
    fi
fi

# Same rule as scripts/jmeter-data.sh: the day after the last seeded reservation,
# or today (UTC, postgres container) when that day is already in the past.
# Passed with -J so a ranges.properties generated earlier cannot go stale.
ep9_start=""
if [ "$scenario" = s2 ]; then
    max_reservation=$(docker compose exec -T postgres sh -c \
        'psql -U "$POSTGRES_USER" -d laravel_app_template -v ON_ERROR_STOP=1 -X -q -A -t -c "SELECT MAX(reservation_date) FROM reservations"')
    max_reservation="${max_reservation//[[:space:]]/}"
    today=$(docker compose exec -T postgres date -u +%F)
    today="${today//$'\r'/}"
    ep9_start=$(date -u -d "${max_reservation} + 1 day" +%F)
    if [[ "$ep9_start" < "$today" ]]; then
        ep9_start="$today"
    fi
fi

jmeter() {
    docker compose --profile loadtest run --rm -T --no-deps jmeter \
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
    local ids
    ids=$(docker compose ps -q "$app" "$nginx" postgres | tr '\n' ' ')
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

# JMeter timestamps come from the Docker Desktop VM clock, stats.csv from this
# shell's clock (WSL), and the two drift apart. The offset (VM minus WSL, seconds)
# lets summarize.py cut stats.csv to the exact load window seen in results.jtl.
clock_offset() {
    local t0 vm t1
    t0="$EPOCHREALTIME"
    vm=$(docker compose exec -T postgres date +%s.%N)
    t1="$EPOCHREALTIME"
    awk -v a="$t0" -v b="$t1" -v v="$vm" 'BEGIN { printf "%.3f", v - (a + b) / 2 }'
}

pool_size="n/a"
[ "$framework" = nestjs ] && pool_size=$(docker compose exec -T nestjs-app printenv DB_POOL_SIZE)
app_cpus=$(awk -v n="$(inspect '{{.HostConfig.NanoCpus}}')" 'BEGIN { print n / 1e9 }')
app_mem_mib=$(( $(inspect '{{.HostConfig.Memory}}') / 1024 / 1024 ))
image=$(inspect '{{.Image}}')

total=$(( ${#endpoints[@]} * ${#users[@]} * REPS ))
per_run=$(( WARMUP + DURATION + 30 ))
done_runs=0

# Warm-up and measurement are separate JMeter processes on the same database, so
# EP9's slot counter would otherwise start at zero twice and the measurement would
# collide with reservations created during warm-up. 100000000 slots is about 28
# years further along the 200 x 48 grid.
warmup_ep9=()
measure_ep9=()
if [ "$scenario" = s2 ]; then
    warmup_ep9=(-Jep9.start="$ep9_start" -Jep9.offset=0)
    measure_ep9=(-Jep9.start="$ep9_start" -Jep9.offset=100000000)
fi

for ep in "${endpoints[@]}"; do
    for vu in "${users[@]}"; do
        for rep in $(seq 1 "$REPS"); do
            rel="${out_name}/${framework}/${ep}/vu${vu}/rep$(printf '%02d' "$rep")"
            dir="results/${rel}"
            container_dir="/results/${rel}"
            done_runs=$((done_runs + 1))
            if grep -qs '"status": "complete"' "${dir}/meta.json"; then
                # Resume only a series with the same parameters; e.g. a smoke test must
                # not be counted as the first repetition of a real series.
                if ! grep -q "\"warmup_s\": ${WARMUP}," "${dir}/meta.json" \
                    || ! grep -q "\"duration_s\": ${DURATION}," "${dir}/meta.json" \
                    || ! grep -q "\"rampup_s\": ${RAMPUP}," "${dir}/meta.json" \
                    || ! grep -q "\"db_pool_size\": \"${pool_size}\"," "${dir}/meta.json"; then
                    echo "${dir} holds a run with different WARMUP/DURATION/RAMPUP or DB_POOL_SIZE; move it away first." >&2
                    exit 1
                fi
                echo "[${done_runs}/${total}] ${dir}: already complete, skipped"
                continue
            fi
            rm -rf "$dir" && mkdir -p "$dir"

            eta=$(( (total - done_runs + 1) * per_run / 60 ))
            echo "[${done_runs}/${total}] ${framework} ${out_name} ${ep} vu=${vu} rep=${rep} (about ${eta} min left)"

            scripts/db-reset.sh "$framework" >/dev/null

            jmeter -Jendpoint="$ep" -Jusers="$vu" -Jduration="$WARMUP" \
                "${warmup_ep9[@]}" \
                -j "${container_dir}/warmup.log" >/dev/null

            offset=$(clock_offset)
            start_stats "${dir}/stats.csv"
            started="$EPOCHREALTIME"
            status=complete
            jmeter -Jendpoint="$ep" -Jusers="$vu" -Jduration="$DURATION" \
                "${measure_ep9[@]}" \
                -l "${container_dir}/results.jtl" -j "${container_dir}/jmeter.log" >/dev/null || status=failed
            finished="$EPOCHREALTIME"
            stop_stats

            if ! grep -q ',SETUP_login,200,' "${dir}/results.jtl" 2>/dev/null; then
                status=failed
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
  "app_memory_mib": ${app_mem_mib},
  "db_pool_size": "${pool_size}",
  "app_image": "${image}"
}
EOF
            if [ "$status" != complete ]; then
                echo "Run failed, see ${dir}/jmeter.log and ${dir}/results.jtl" >&2
                exit 1
            fi
        done
    done
done

echo "Done: results/${out_name}/${framework}"
