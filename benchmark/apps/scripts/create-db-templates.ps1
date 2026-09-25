# Wrapper around create-db-templates.php (psql is not required on PATH).
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'create-db-templates.php'
& php $script
