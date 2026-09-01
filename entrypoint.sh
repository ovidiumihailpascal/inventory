#!/bin/bash
set -e
echo "Inventory Application - Starting up..."

if [ -n "$DB_HOST" ]; then
    echo "PostgreSQL mode detected"
    echo "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if pg_isready -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "${DB_USER:-inventory_app}" > /dev/null 2>&1; then
            echo "PostgreSQL is ready!"
            break
        fi
        echo "Attempt $i/30 - PostgreSQL not ready, waiting..."
        sleep 2
    done
fi

echo "Starting application with production WSGI server (Gunicorn)..."
# Execute the CMD passed from Dockerfile/docker-compose
exec "$@"