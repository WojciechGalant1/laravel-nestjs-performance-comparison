<?php

/**
 * Restore working databases from their templates.
 * Run before every scenario repetition so EP7/EP9 mutations are wiped.
 *
 * Usage:
 *   php apps/scripts/reset-databases.php
 *   php apps/scripts/reset-databases.php nestjs
 *   php apps/scripts/reset-databases.php laravel
 */

$which = $argv[1] ?? 'both';

$envPath = dirname(__DIR__).'/laravel-app/.env';
$env = [];

foreach (file($envPath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
    if ($line[0] === '#' || ! str_contains($line, '=')) {
        continue;
    }
    [$key, $value] = explode('=', $line, 2);
    $env[trim($key)] = trim($value);
}

$host = $env['DB_HOST'] ?? '127.0.0.1';
$port = $env['DB_PORT'] ?? '5432';
$user = $env['DB_USERNAME'] ?? 'postgres';
$password = $env['DB_PASSWORD'] ?? '';

$conn = pg_connect("host={$host} port={$port} dbname=postgres user={$user} password={$password}");

if ($conn === false) {
    fwrite(STDERR, "Failed to connect to PostgreSQL.\n");
    exit(1);
}

function pg(PgSql\Connection $conn, string $sql): void
{
    if (pg_query($conn, $sql) === false) {
        fwrite(STDERR, pg_last_error($conn)."\nSQL: {$sql}\n");
        exit(1);
    }
}

function resetDatabase(PgSql\Connection $conn, string $name): void
{
    $template = $name.'_template';
    echo "Resetting {$name} from {$template} ...\n";
    pg($conn, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{$name}' AND pid <> pg_backend_pid()");
    pg($conn, "DROP DATABASE IF EXISTS {$name}");
    pg($conn, "CREATE DATABASE {$name} TEMPLATE {$template}");
}

if ($which === 'both' || $which === 'laravel') {
    resetDatabase($conn, 'laravel_app');
}
if ($which === 'both' || $which === 'nestjs') {
    resetDatabase($conn, 'nestjs_app');
}

echo "Reset complete.\n";
