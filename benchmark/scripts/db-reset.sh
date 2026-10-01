#!/usr/bin/env bash
# Restore working databases from their templates and restart the application
# containers, as required before every scenario repetition: the reset wipes the
# EP7/EP9 mutations and the restart clears in-process state (OPcache/JIT and V8
# warm-up, connection pools), so each repetition starts from the same point.
#
# Usage: scripts/db-reset.sh [laravel|nestjs|both]   (default: both)
set -euo pipefail

cd "$(dirname "$0")/.."

which="${1:-both}"

case "$which" in
    laravel) names=(laravel_app) ;;
    nestjs) names=(nestjs_app) ;;
    both) names=(laravel_app nestjs_app) ;;
    *) echo "Usage: $0 [laravel|nestjs|both]" >&2; exit 1 ;;
esac

for name in "${names[@]}"; do
    echo "Resetting ${name} from ${name}_template ..."
    docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -q -o /dev/null' <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname = '${name}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${name};
CREATE DATABASE ${name} TEMPLATE ${name}_template;
SQL
done

# Only restarts what is already running, so resetting "both" works while a single
# stack is up (the normal case during a measurement).
restart_stack() {
    local profile="$1" app="$2" nginx="$3" probe="$4"

    if [ -z "$(docker compose ps -q --status running "$app")" ]; then
        return 0
    fi

    echo "Restarting ${app} ..."
    docker compose --profile "$profile" restart "$app" >/dev/null
    # nginx resolves the app address only at startup; restarting it as well keeps
    # it valid after the app container was recreated (e.g. after a rebuild).
    docker compose --profile "$profile" restart "$nginx" >/dev/null
    # --no-recreate: this step only waits for the healthchecks, it must not
    # rebuild or replace containers in the middle of a measurement series.
    docker compose --profile "$profile" up -d --wait --no-recreate "$app" "$nginx" >/dev/null
    # nginx stays "healthy" across the app restart, so --wait can return before
    # the app accepts connections; probe the app through nginx instead.
    local i
    for i in $(seq 1 60); do
        if docker compose exec -T "$nginx" curl -fsS -o /dev/null "http://localhost${probe}" 2>/dev/null; then
            return 0
        fi
        sleep 1
    done
    echo "${app} did not answer through ${nginx} within 60 s" >&2
    exit 1
}

for name in "${names[@]}"; do
    case "$name" in
        laravel_app) restart_stack laravel laravel-app laravel-nginx /up ;;
        nestjs_app) restart_stack nestjs nestjs-app nestjs-nginx / ;;
    esac
done

if [ -n "$(docker compose ps -q --status running laravel-app)" ] \
    && [ -n "$(docker compose ps -q --status running nestjs-app)" ]; then
    echo "WARNING: both application stacks are running; they share the same CPUs." >&2
    echo "Stop the one you are not measuring: docker compose stop <stack>-app <stack>-nginx" >&2
fi

echo "Reset complete."
