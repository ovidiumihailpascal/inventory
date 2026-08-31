#!/bin/bash
# PostgreSQL Restore Script
# Usage: ./scripts/restore-postgres.sh <backup-file>
# Example: ./scripts/restore-postgres.sh ./backups/postgres/inventory_20240101_120000.sql

set -e

# Check if backup file argument provided
if [ $# -ne 1 ]; then
  echo "Usage: $0 <backup-file>"
  echo "Example: $0 ./backups/postgres/inventory_20240101_120000.sql"
  exit 1
fi

BACKUP_FILE="$1"

# Verify backup file exists and has content
if [ ! -f "$BACKUP_FILE" ] || [ ! -s "$BACKUP_FILE" ]; then
  echo "✗ Error: Backup file not found or empty: $BACKUP_FILE"
  exit 1
fi

# Get configuration from environment or defaults
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-inventory}"
DB_USER="${DB_USER:-inventory_app}"
DB_PASSWORD="${DB_PASSWORD:-}"

echo "WARNING: This will restore the database from backup."
echo "All current data in '$DB_NAME' will be replaced."
echo "Backup file: $BACKUP_FILE"
echo ""
read -p "Are you sure you want to proceed? Type 'yes' to confirm: " -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo "Restore cancelled."
  exit 1
fi

echo ""
echo "Starting PostgreSQL restore..."

# Set password for psql
export PGPASSWORD="$DB_PASSWORD"

# Drop existing database and recreate it
echo "Recreating database..."
psql \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="postgres" \
  --no-password \
  -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" \
  -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";"

# Restore from backup
echo "Restoring data from backup..."
psql \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --no-password \
  "$DB_NAME" < "$BACKUP_FILE"

echo "✓ Restore complete!"
echo "Database '$DB_NAME' has been restored from $BACKUP_FILE"
