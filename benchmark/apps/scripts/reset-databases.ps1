param(
    [ValidateSet('both', 'laravel', 'nestjs')]
    [string]$App = 'both'
)

$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'reset-databases.php'
& php $script $App
