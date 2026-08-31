#!/bin/bash
# PostgreSQL Backup Script
# Usage: ./scripts/backup-postgres.sh
# Creates timestamped backups in ./backups/postgres/

set -e

# Get configuration from environment or defaults
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-inventory}"
DB_USER="${DB_USER:-inventory_app}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Create backup directory
BACKUP_DIR="./backups/postgres"
mkdir -p "$BACKUP_DIR"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/inventory_${TIMESTAMP}.sql"

echo "Starting PostgreSQL backup..."
echo "Database: $DB_NAME"
echo "Backup file: $BACKUP_FILE"

# Set password for pg_dump
export PGPASSWORD="$DB_PASSWORD"

# Perform backup with pg_dump
pg_dump \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --verbose \
  --no-password \
  "$DB_NAME" > "$BACKUP_FILE"

# Verify backup was created and has content
if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
  echo "✓ Backup successful: $BACKUP_FILE ($(wc -c < "$BACKUP_FILE") bytes)"
  
  # Keep only the last 10 backups to save disk space
  echo "Cleaning up old backups (keeping last 10)..."
  ls -t "$BACKUP_DIR"/inventory_*.sql | tail -n +11 | xargs -r rm
  
  echo "✓ Backup complete!"
  exit 0
else
  echo "✗ Backup failed: File not created or empty"
  exit 1
fi
