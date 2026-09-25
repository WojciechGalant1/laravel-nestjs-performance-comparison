#!/bin/sh
set -e

# Built at container start, not in the image: config:cache freezes the
# environment variables injected by docker compose.
php artisan config:cache
php artisan route:cache

exec "$@"
