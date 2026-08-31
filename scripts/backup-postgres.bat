@echo off
REM PostgreSQL Backup Script for Windows
REM Usage: backup-postgres.bat
REM Creates timestamped backups in backups\postgres\

setlocal enabledelayedexpansion

REM Get configuration from environment or defaults
if not defined DB_HOST set "DB_HOST=localhost"
if not defined DB_PORT set "DB_PORT=5432"
if not defined DB_NAME set "DB_NAME=inventory"
if not defined DB_USER set "DB_USER=inventory_app"
if not defined DB_PASSWORD set "DB_PASSWORD="

REM Create backup directory
set "BACKUP_DIR=backups\postgres"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Generate timestamp (YYYYMMDD_HHMMSS)
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set "TIMESTAMP=!mydate!_!mytime!"
set "BACKUP_FILE=!BACKUP_DIR!\inventory_!TIMESTAMP!.sql"

echo Starting PostgreSQL backup...
echo Database: %DB_NAME%
echo Backup file: %BACKUP_FILE%

REM Set password environment variable for pg_dump
set "PGPASSWORD=%DB_PASSWORD%"

REM Perform backup with pg_dump
pg_dump ^
  --host=%DB_HOST% ^
  --port=%DB_PORT% ^
  --username=%DB_USER% ^
  --verbose ^
  --no-password ^
  %DB_NAME% > "%BACKUP_FILE%"

REM Verify backup was created
if exist "%BACKUP_FILE%" (
  echo ✓ Backup successful: %BACKUP_FILE%
  echo ✓ Backup complete!
  exit /b 0
) else (
  echo ✗ Backup failed: File not created
  exit /b 1
)
