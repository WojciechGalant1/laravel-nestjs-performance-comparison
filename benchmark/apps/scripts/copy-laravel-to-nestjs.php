<?php

/**
 * Clone laravel_app into nestjs_app using PostgreSQL's TEMPLATE copy
 * (schema, enums, constraints, sequences, and all rows).
 *
 * Usage: php apps/scripts/copy-laravel-to-nestjs.php
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

$terminate = <<<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname IN ('laravel_app', 'nestjs_app')
  AND pid <> pg_backend_pid()
SQL;

if (pg_query($conn, $terminate) === false) {
    fwrite(STDERR, 'terminate failed: '.pg_last_error($conn)."\n");
    exit(1);
}

if (pg_query($conn, 'DROP DATABASE IF EXISTS nestjs_app') === false) {
    fwrite(STDERR, 'DROP DATABASE failed: '.pg_last_error($conn)."\n");
    exit(1);
}

if (pg_query($conn, 'CREATE DATABASE nestjs_app TEMPLATE laravel_app') === false) {
    fwrite(STDERR, 'CREATE DATABASE failed: '.pg_last_error($conn)."\n");
    exit(1);
}

echo "Created nestjs_app as a byte-for-byte copy of laravel_app.\n";
