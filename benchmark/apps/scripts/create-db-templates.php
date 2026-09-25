<?php

/**
 * Create *_template databases from the seeded working copies.
 * Run once after laravel_app is seeded and copied to nestjs_app.
 *
 * Usage: php apps/scripts/create-db-templates.php
 */

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

foreach (['laravel_app', 'nestjs_app'] as $name) {
    $template = $name.'_template';
    echo "Recreating {$template} from {$name} ...\n";

    pg($conn, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('{$name}', '{$template}') AND pid <> pg_backend_pid()");
    pg($conn, "DROP DATABASE IF EXISTS {$template}");
    pg($conn, "CREATE DATABASE {$template} TEMPLATE {$name}");
}

echo "Templates ready: laravel_app_template, nestjs_app_template.\n";
