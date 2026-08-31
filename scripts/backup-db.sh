#!/bin/bash
# PostgreSQL Backup Script for Inventory Application
# This script creates timestamped backups of the PostgreSQL database
# Usage: ./scripts/backup-db.sh

set -e

# Configuration
BACKUP_DIR="./backups/postgres"
MAX_BACKUPS=30  # Keep only the last 30 backups
CONTAINER_NAME="inventory_postgres"
DB_NAME="${DB_NAME:-inventory}"
DB_USER="${DB_USER:-inventory_app}"
DB_PASSWORD="${DB_PASSWORD}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate timestamp for backup filename
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="$BACKUP_DIR/inventory_backup_${TIMESTAMP}.sql"

echo "=========================================="
echo "PostgreSQL Database Backup"
echo "=========================================="
echo "Database: $DB_NAME"
echo "Container: $CONTAINER_NAME"
echo "Backup file: $BACKUP_FILE"
echo "Time: $(date)"
echo "=========================================="

# Check if Docker container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "ERROR: PostgreSQL container '$CONTAINER_NAME' is not running!"
    exit 1
fi

# Create backup using pg_dump inside the container
docker exec -e PGPASSWORD="$DB_PASSWORD" "$CONTAINER_NAME" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✓ Backup created successfully: $BACKUP_FILE"
    echo "✓ File size: $(du -h "$BACKUP_FILE" | cut -f1)"
    
    # Compress the backup
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"
    echo "✓ Backup compressed: $BACKUP_FILE"
    echo "✓ Compressed size: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "✗ Backup failed!"
    exit 1
fi

# Clean up old backups (keep only the last MAX_BACKUPS)
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/inventory_backup_*.sql.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
    echo ""
    echo "Cleaning up old backups (keeping last $MAX_BACKUPS)..."
    ls -1t "$BACKUP_DIR"/inventory_backup_*.sql.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | while read -r old_backup; do
        echo "  Removing: $(basename "$old_backup")"
        rm -f "$old_backup"
    done
fi

echo ""
echo "=========================================="
echo "Backup completed successfully!"
echo "=========================================="
