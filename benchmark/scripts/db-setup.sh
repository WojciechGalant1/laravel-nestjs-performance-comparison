#!/usr/bin/env bash
# One-time database setup: migrate and seed laravel_app, clone it to nestjs_app,
# then snapshot both as *_template for db-reset.sh.
#
# Usage: scripts/db-setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."

psql() {
    docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -q -o /dev/null'
}

docker compose up -d --wait postgres

echo "Migrating and seeding laravel_app ..."
docker compose --profile setup run --rm --build laravel-tools \
    php artisan migrate:fresh --seed --force

echo "Cloning laravel_app into nestjs_app ..."
psql <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname IN ('laravel_app', 'nestjs_app') AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS nestjs_app;
CREATE DATABASE nestjs_app TEMPLATE laravel_app;
SQL

for name in laravel_app nestjs_app; do
    echo "Recreating ${name}_template from ${name} ..."
    psql <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname IN ('${name}', '${name}_template') AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${name}_template;
CREATE DATABASE ${name}_template TEMPLATE ${name};
SQL
done

echo "Setup complete: laravel_app, nestjs_app and their *_template copies are ready."
