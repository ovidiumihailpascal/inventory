@echo off
REM PostgreSQL Restore Script for Windows
REM Usage: restore-postgres.bat <backup-file>
REM Example: restore-postgres.bat backups\postgres\inventory_20240101_120000.sql

setlocal enabledelayedexpansion

if "%1"=="" (
  echo Usage: %0 ^<backup-file^>
  echo Example: %0 backups\postgres\inventory_20240101_120000.sql
  exit /b 1
)

set "BACKUP_FILE=%1"

REM Verify backup file exists
if not exist "%BACKUP_FILE%" (
  echo ✗ Error: Backup file not found: %BACKUP_FILE%
  exit /b 1
)

REM Get configuration from environment or defaults
if not defined DB_HOST set "DB_HOST=localhost"
if not defined DB_PORT set "DB_PORT=5432"
if not defined DB_NAME set "DB_NAME=inventory"
if not defined DB_USER set "DB_USER=inventory_app"
if not defined DB_PASSWORD set "DB_PASSWORD="

echo WARNING: This will restore the database from backup.
echo All current data in '%DB_NAME%' will be replaced.
echo Backup file: %BACKUP_FILE%
echo.
set /p CONFIRM="Are you sure you want to proceed? Type 'yes' to confirm: "

if /i not "%CONFIRM%"=="yes" (
  echo Restore cancelled.
  exit /b 1
)

echo.
echo Starting PostgreSQL restore...

REM Set password environment variable for psql
set "PGPASSWORD=%DB_PASSWORD%"

REM Drop existing database and recreate it
echo Recreating database...
psql ^
  --host=%DB_HOST% ^
  --port=%DB_PORT% ^
  --username=postgres ^
  --no-password ^
  -c "DROP DATABASE IF EXISTS \"%DB_NAME%\";" ^
  -c "CREATE DATABASE \"%DB_NAME%\" OWNER \"%DB_USER%\";"

if errorlevel 1 (
  echo ✗ Failed to recreate database
  exit /b 1
)

REM Restore from backup
echo Restoring data from backup...
psql ^
  --host=%DB_HOST% ^
  --port=%DB_PORT% ^
  --username=%DB_USER% ^
  --no-password ^
  %DB_NAME% < "%BACKUP_FILE%"

if errorlevel 1 (
  echo ✗ Restore failed
  exit /b 1
)

echo ✓ Restore complete!
echo Database '%DB_NAME%' has been restored from %BACKUP_FILE%
