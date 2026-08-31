#!/bin/bash
# PostgreSQL Restore Script for Inventory Application
# This script restores a PostgreSQL database from a backup file
# Usage: ./scripts/restore-db.sh ./backups/postgres/inventory_backup_20240101_120000.sql.gz

set -e

BACKUP_FILE="$1"
CONTAINER_NAME="inventory_postgres"
DB_NAME="${DB_NAME:-inventory}"
DB_USER="${DB_USER:-inventory_app}"
DB_PASSWORD="${DB_PASSWORD}"

echo "=========================================="
echo "PostgreSQL Database Restore"
echo "=========================================="

# Validate input
if [ -z "$BACKUP_FILE" ]; then
    echo "ERROR: No backup file specified!"
    echo "Usage: $0 <backup-file>"
    echo ""
    echo "Available backups:"
    ls -lh ./backups/postgres/inventory_backup_*.sql* 2>/dev/null || echo "No backups found"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Backup file: $BACKUP_FILE"
echo "Database: $DB_NAME"
echo "Container: $CONTAINER_NAME"
echo "=========================================="
echo ""

# Check if Docker container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "ERROR: PostgreSQL container '$CONTAINER_NAME' is not running!"
    echo "Start it with: docker compose up -d postgres"
    exit 1
fi

# Ask for confirmation
echo "WARNING: This will OVERWRITE the current database!"
read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo "Restoring database..."

# Determine if the backup is compressed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Decompressing and restoring..."
    gunzip -c "$BACKUP_FILE" | docker exec -i -e PGPASSWORD="$DB_PASSWORD" "$CONTAINER_NAME" \
        psql -U "$DB_USER" -d "$DB_NAME"
else
    echo "Restoring from uncompressed backup..."
    docker exec -i -e PGPASSWORD="$DB_PASSWORD" "$CONTAINER_NAME" \
        psql -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE"
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Database restored successfully!"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "✗ Restore failed!"
    echo "=========================================="
    exit 1
fi
