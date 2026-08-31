# Docker Deployment Guide - Inventory Management System

## Overview

This guide provides comprehensive instructions for deploying the Inventory Management System using Docker Compose with PostgreSQL persistence, backups, and disaster recovery procedures.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Compose Network                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐              ┌──────────────────┐          │
│  │  inventory-app   │◄────────────►│  postgres        │          │
│  │  (Flask App)     │              │  (PostgreSQL)    │          │
│  │  Port: 5000      │              │  Port: 5432      │          │
│  │  (Disposable)    │              │  (Persistent)    │          │
│  └──────────────────┘              └──────────────────┘          │
│                                     │                             │
│                                     ▼                             │
│                            ┌─────────────────┐                   │
│                            │ Named Volume    │                   │
│                            │ inventory_      │                   │
│                            │ postgres_data   │                   │
│                            │ (Host Storage)  │                   │
│                            └─────────────────┘                   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  Backup Storage (Host: ./backups/postgres/)          │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Architectural Principles

✅ **Application Container is DISPOSABLE**
- Can be stopped, removed, rebuilt, and recreated without data loss
- Stateless - all state is stored in PostgreSQL
- Safe to deploy new versions by replacing the container

✅ **PostgreSQL Container is PERSISTENT**
- Data stored in named Docker volume `inventory_postgres_data`
- Volume exists independently of containers
- Survives container recreation and image rebuilds

✅ **Backups are AUTOMATED**
- PostgreSQL backups created on a schedule
- Stored outside containers in `./backups/postgres/`
- Multiple historical backups retained

---

## Prerequisites

1. **Docker** - version 20.10+
2. **Docker Compose** - version 2.0+
3. **PostgreSQL Client** (psql, pg_dump) - for backups and manual administration
4. **.env file** - configured with production passwords

## Initial Setup

### 1. Clone Repository and Navigate

```bash
cd /path/to/inventory
```

### 2. Create Environment File

Copy the example and configure for your environment:

```bash
cp .env.example .env
```

**Edit .env and change these critical values:**

```env
# Database password - use a strong, random password
DB_PASSWORD=your-secure-random-password-here

# Flask secret key - use a random value
FLASK_SECRET=your-random-secret-key-here

# Admin credentials - change immediately after first login
INVENTORY_USER=admin
INVENTORY_PASS=your-secure-password-here

# Application port (optional, default 5000)
APP_PORT=5000
```

**⚠️ SECURITY NOTE:** Never commit `.env` to version control. It's in `.gitignore` for a reason.

### 3. Verify .gitignore

Ensure these files are NOT committed:

```bash
# Check .gitignore contains:
.env                          # Environment variables with passwords
instance/inventory.db         # Local SQLite (development only)
backups/                      # Database backups
__pycache__/                  # Python bytecode
*.pyc                         # Python compiled files
```

---

## Deployment Procedures

### Safe Operations (These are ALWAYS safe - data is preserved)

#### Start Services
```bash
docker compose up -d
```
- Starts all services
- Creates volumes and networks if needed
- PostgreSQL data is preserved
- Safe to run repeatedly

#### Rebuild and Restart Application
```bash
docker compose up -d --build inventory-app
```
- Rebuilds only the Python application image
- PostgreSQL and data untouched
- Safe deployment of new versions
- Data preserved

#### Stop Services
```bash
docker compose stop
```
- Gracefully stops all containers
- Data remains in volumes
- Safe to resume with `docker compose start`

#### Restart Services
```bash
docker compose restart
```
- Restarts all containers
- Data preserved
- Idempotent - safe to run multiple times

#### View Logs
```bash
docker compose logs -f inventory-app
docker compose logs -f postgres
```

#### Run Database Backup
```bash
# Linux/macOS
./scripts/backup-postgres.sh

# Windows
scripts\backup-postgres.bat
```
- Creates timestamped backup in `./backups/postgres/`
- Can be run while services are running
- Keeps last 10 backups automatically

---

### ⚠️ DESTRUCTIVE Operations (These DELETE data)

#### Remove Application Container Only
```bash
docker compose rm -f inventory-app
```
- Removes application container only
- PostgreSQL and data preserved
- Safe for cleanup before deployment

#### Stop and Remove All Containers (Data Preserved)
```bash
docker compose down
```
- Stops and removes all containers
- **Volumes (data) are preserved**
- Safe - data not deleted
- Resume with `docker compose up -d`

#### ❌ EXTREMELY DESTRUCTIVE - Delete Everything Including Data
```bash
docker compose down -v
```

**⚠️ WARNING: This command deletes:**
- All containers
- All networks
- All volumes including `inventory_postgres_data`
- **ALL DATABASE DATA - PERMANENT DATA LOSS**

**This should ONLY be used if:**
- You have recent backups
- You intentionally want to destroy everything
- You're completely reinstalling from scratch

**You almost never want to use this command.**

---

## Backup and Recovery

### Automated Backups

Create a scheduled backup (Linux/macOS crontab):

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM (adjust time as needed)
0 2 * * * cd /path/to/inventory && ./scripts/backup-postgres.sh >> ./backups/backup.log 2>&1
```

Or use Docker's built-in scheduling:

```bash
# Create a backup service in docker-compose.yml (optional)
# See examples in docker-compose.yml.backup
```

### Manual Backup

```bash
# Linux/macOS
./scripts/backup-postgres.sh

# Windows
scripts\backup-postgres.bat
```

### Restore from Backup

```bash
# List available backups
ls -lh backups/postgres/

# Restore specific backup
./scripts/restore-postgres.sh ./backups/postgres/inventory_20240115_020000.sql

# Windows
scripts\restore-postgres.bat backups\postgres\inventory_20240115_020000.sql
```

---

## Disaster Recovery

### Scenario 1: Application Container Crashed

**Symptom:** Application not responding

**Recovery:**
```bash
# Restart the application container
docker compose restart inventory-app

# Verify it's running
docker compose ps

# Check logs
docker compose logs -f inventory-app
```

**Expected result:** Application restarts, data intact, all inventory records preserved.

---

### Scenario 2: PostgreSQL Container Crashed

**Symptom:** Application shows database connection errors

**Recovery:**
```bash
# Restart PostgreSQL
docker compose restart postgres

# Verify it's running and healthy
docker compose ps

# Wait for health check to pass (may take 10-30 seconds)
docker compose logs postgres

# Application should reconnect automatically
docker compose logs inventory-app
```

**Expected result:** PostgreSQL restarts and mounts the volume with all data intact.

---

### Scenario 3: Server Fails, Need to Rebuild from Scratch

**Prerequisites:** Recent backup file exists in `./backups/postgres/`

**Step 1: Set Up New Server**
```bash
# 1. Install Docker and Docker Compose on new server
sudo apt-get install docker.io docker-compose

# 2. Clone the repository
git clone <repo-url>
cd inventory

# 3. Create .env file
cp .env.example .env
# Edit .env with secure passwords
nano .env
```

**Step 2: Start Database (Empty)**
```bash
# Start PostgreSQL container only
docker compose up -d postgres

# Wait for database to be ready
docker compose logs postgres
# Look for: "database system is ready to accept connections"

# Give it a few seconds
sleep 10
```

**Step 3: Restore from Backup**
```bash
# Linux/macOS
./scripts/restore-postgres.sh ./backups/postgres/inventory_YYYYMMDD_HHMMSS.sql

# Windows
scripts\restore-postgres.bat backups\postgres\inventory_YYYYMMDD_HHMMSS.sql
```

**Step 4: Start Application**
```bash
docker compose up -d inventory-app

# Verify it's connected to database
docker compose logs inventory-app
# Should see: "Database connected" or similar

# Verify web interface
curl http://localhost:5000
```

**Expected result:** All inventory data restored, application running, users can log in.

---

### Scenario 4: Need to Update Application Code

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Rebuild and Redeploy (Application Only)**
```bash
docker compose up -d --build inventory-app
```

**Step 3: Verify**
```bash
docker compose logs -f inventory-app
# Wait for startup messages
# Application should connect to existing database

# Visit web interface
# All inventory data should be present
```

**Expected result:** New code running, all data intact, seamless deployment.

---

## Database Migrations

When schema changes are needed:

### Method 1: Direct SQL Updates (For Simple Changes)

```bash
# Connect to database
docker compose exec postgres psql -U inventory_app inventory

# Run SQL commands
ALTER TABLE items ADD COLUMN description TEXT;

# Exit
\q
```

### Method 2: Using Migration Script

Create `migrations/002_add_column_example.sql`:

```sql
-- Migration: Add description column to items
ALTER TABLE items ADD COLUMN description TEXT DEFAULT NULL;

-- Add index for new column
CREATE INDEX idx_items_description ON items(description);
```

Then apply:

```bash
# Connect to database
docker compose exec postgres psql -U inventory_app inventory < migrations/002_add_column_example.sql
```

---

## Troubleshooting

### Issue: Application Won't Start

```bash
# Check logs
docker compose logs inventory-app

# Common causes:
# 1. Database not ready - wait 30 seconds
# 2. Invalid .env configuration
# 3. Database password mismatch
# 4. Port 5000 already in use

# Solution: Check .env and try restarting
docker compose restart
```

### Issue: Cannot Connect to Database

```bash
# Check PostgreSQL is running
docker compose logs postgres

# Verify password in .env matches
cat .env | grep DB_PASSWORD

# Test connection manually
docker compose exec postgres psql -U inventory_app -c "SELECT 1"

# If password wrong:
# 1. Stop everything
docker compose down

# 2. Delete the volume (data loss!)
docker volume rm inventory_inventory_postgres_data

# 3. Update .env with correct password
nano .env

# 4. Start fresh
docker compose up -d
```

### Issue: Out of Disk Space

```bash
# Check volume usage
docker volume ls
docker system df

# Old backups taking space?
ls -lh backups/postgres/
# Delete old backups manually
rm backups/postgres/inventory_old_*.sql
```

### Issue: Performance Degradation

```bash
# Check container resources
docker stats

# Increase memory limit in docker-compose.yml
# Add under postgres service:
# deploy:
#   resources:
#     limits:
#       memory: 2G

# Restart
docker compose up -d
```

---

## Maintenance

### Weekly Tasks

✅ Verify backup was created
```bash
ls -lh backups/postgres/
```

✅ Check application logs for errors
```bash
docker compose logs inventory-app | grep -i error
```

### Monthly Tasks

✅ Test backup restoration procedure
```bash
# Take a backup of current state first
./scripts/backup-postgres.sh

# Restore to test it works
./scripts/restore-postgres.sh ./backups/postgres/inventory_*.sql

# Verify data is intact
# Then restore the backup taken before this test
```

✅ Review and update .env passwords if needed

✅ Update application code and dependencies
```bash
git pull
docker compose up -d --build
```

### Yearly Tasks

✅ Full server maintenance and updates
✅ Backup rotation and archival
✅ Security audit

---

## Production Checklist

Before deploying to production:

- [ ] Change all default passwords in .env
- [ ] Set FLASK_ENV=production in .env
- [ ] Use strong, random passwords (at least 20 characters)
- [ ] Test full backup and restore procedure
- [ ] Set up automated backup cron job
- [ ] Configure container resource limits
- [ ] Set up monitoring/alerting
- [ ] Document any custom configuration
- [ ] Test disaster recovery procedure
- [ ] Review firewall rules (only 5000 exposed)
- [ ] Enable HTTPS/SSL if accessible from internet
- [ ] Create regular backup retention policy

---

## Reference

### Docker Compose Commands

| Command | Effect | Data Safety |
|---------|--------|------------|
| `up` | Start services | ✅ Safe |
| `down` | Stop and remove containers | ✅ Safe (volumes preserved) |
| `down -v` | Remove everything including data | ❌ **DESTRUCTIVE** |
| `restart` | Restart containers | ✅ Safe |
| `stop` | Stop containers (keep running) | ✅ Safe |
| `start` | Resume stopped containers | ✅ Safe |
| `rm` | Remove containers | ✅ Safe (data in volumes) |
| `logs` | View container logs | ✅ Safe |
| `exec` | Run command in container | ⚠️ Depends on command |

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| DB_HOST | postgres | PostgreSQL hostname |
| DB_PORT | 5432 | PostgreSQL port |
| DB_NAME | inventory | Database name |
| DB_USER | inventory_app | Database user |
| DB_PASSWORD | *required* | Database password |
| FLASK_ENV | production | Flask environment |
| FLASK_SECRET | *required* | Flask session secret |
| INVENTORY_USER | admin | App admin username |
| INVENTORY_PASS | *required* | App admin password |
| APP_PORT | 5000 | Application port |

---

## Support

For issues or questions:
1. Check Docker logs: `docker compose logs`
2. Review this guide's troubleshooting section
3. Test backup/restore procedures
4. Check PostgreSQL database directly for data integrity

---

**Last Updated:** 2024-01-15
**Version:** 1.0
**Status:** Production Ready
