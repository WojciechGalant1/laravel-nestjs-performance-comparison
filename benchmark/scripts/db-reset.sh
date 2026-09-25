#!/usr/bin/env bash
# Restore working databases from their templates.
# Run before every scenario repetition so EP7/EP9 mutations are wiped.
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

echo "Reset complete."
