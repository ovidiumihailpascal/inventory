#!/bin/bash
# Docker entrypoint script for Inventory application
# Handles database initialization and application startup

set -e

echo "Inventory Application - Starting up..."

# Check if we're using PostgreSQL (Docker) or SQLite (local)
if [ -n "$DB_HOST" ]; then
    echo "PostgreSQL mode detected (DB_HOST=$DB_HOST)"
    
    echo "Waiting for PostgreSQL to be ready..."
    # Wait for PostgreSQL to be ready
    until psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "${DB_USER:-inventory_app}" -d "${DB_NAME:-inventory}" -c '\q' 2>/dev/null; do
        echo "PostgreSQL is unavailable - sleeping..."
        sleep 2
    done
    echo "PostgreSQL is ready!"
    
    # Check if tables exist, if not initialize them
    TABLE_COUNT=$(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "${DB_USER:-inventory_app}" -d "${DB_NAME:-inventory}" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" -t)
    
    if [ "$TABLE_COUNT" -lt 4 ]; then
        echo "Tables not found, initializing database schema..."
        psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "${DB_USER:-inventory_app}" -d "${DB_NAME:-inventory}" < /app/init-db.sql
        echo "Database schema initialized!"
    else
        echo "Database tables already exist (found $TABLE_COUNT tables)"
    fi
else
    echo "SQLite mode detected (local development)"
fi

echo "Starting Flask application..."
exec "$@"
