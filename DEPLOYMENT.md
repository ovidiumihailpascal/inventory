# Inventory Application - Docker Deployment Guide

## Architecture Overview

This is a **production-ready** Docker Compose setup for the Inventory application with strict separation between application and persistent data:

```
┌─────────────────────────────────────────┐
│          Docker Compose Network         │
├─────────────────────────────────────────┤
│                                         │
│  ┌────────────────────┐                │
│  │   inventory-app    │                │
│  │  (Disposable)      │                │
│  │  Container         │◄──┐            │
│  └────────────────────┘   │            │
│           ▲                │            │
│           │ Connects via   │            │
│           │ 'postgres'     │            │
│           │ hostname       │            │
│           │                │            │
│  ┌────────┴─────────────┐  │            │
│  │   PostgreSQL         │  │            │
│  │   Container          │──┘            │
│  ├──────────────────────┤               │
│  │ ↓ Data               │               │
│  │                      │               │
│  │ inventory_postgres_  │               │
│  │ data (Named Volume)  │               │
│  │ [PERSISTENT]         │               │
│  └──────────────────────┘               │
│                                         │
└─────────────────────────────────────────┘
```

## Key Features

✅ **Data Persistence**: Database stored in named Docker volume  
✅ **Disposable App Container**: Can be rebuilt and recreated without data loss  
✅ **PostgreSQL Database**: Production-grade relational database  
✅ **Automated Backups**: Scripts to backup and restore data  
✅ **Environment Configuration**: Secure secret management via .env  
✅ **Network Isolation**: Services communicate via Docker network  
✅ **Health Checks**: Built-in container health monitoring  
✅ **Security**: Non-root user in application container  

## Prerequisites

- **Docker** (version 20.10+)
- **Docker Compose** (version 1.29+)
- **bash** (for backup/restore scripts)
- **git** (for version control)

### Check Docker installation

```bash
docker --version      # Should be 20.10+
docker compose version # Should be 1.29+
```

## Quick Start

### 1. Clone or navigate to the project

```bash
cd ~/inventory-app
```

### 2. Create environment file

```bash
cp .env.example .env
```

**⚠️ IMPORTANT**: Edit `.env` and change ALL passwords:

```bash
nano .env  # or your preferred editor
```

At minimum, change:
- `DB_PASSWORD` - PostgreSQL password
- `DB_USER` - Database user
- `FLASK_SECRET` - Flask session secret
- `INVENTORY_USER` - Admin username
- `INVENTORY_PASS` - Admin password

### 3. Start the application

```bash
docker compose up -d
```

This command:
- Builds the application image (if needed)
- Creates the PostgreSQL container
- Creates the `inventory_postgres_data` volume
- Starts both services
- Waits for PostgreSQL health check (max 50 seconds)

### 4. Verify services are running

```bash
docker compose ps
```

Expected output:
```
NAME                COMMAND                  SERVICE          STATUS
inventory_postgres  postgres ...             postgres         Up 2 minutes (healthy)
inventory_app       gunicorn --bind 0.0.0... inventory-app    Up 1 minute (healthy)
```

### 5. Access the application

Open your browser:
- **URL**: http://localhost:5000
- **Username**: (value from `INVENTORY_USER` in .env)
- **Password**: (value from `INVENTORY_PASS` in .env)

## Common Operations

### Start services
```bash
docker compose up -d
```

### Stop services (data persists)
```bash
docker compose stop
```

### Restart services
```bash
docker compose restart
```

### View logs
```bash
docker compose logs -f
```

### View app logs only
```bash
docker compose logs -f inventory-app
```

### View database logs only
```bash
docker compose logs -f postgres
```

### Execute commands in app container
```bash
docker compose exec inventory-app bash
```

### Execute commands in database container
```bash
docker compose exec postgres bash
```

### Connect to PostgreSQL directly
```bash
docker compose exec postgres psql -U $DB_USER -d $DB_NAME
```

## Database Backup and Restore

### Create a backup

```bash
./scripts/backup-db.sh
```

Backups are stored in `./backups/postgres/` with timestamp naming:
```
backups/postgres/
├── inventory_backup_20240101_120000.sql.gz
├── inventory_backup_20240101_130000.sql.gz
└── inventory_backup_20240101_140000.sql.gz
```

The script automatically:
- Compresses backups with gzip
- Keeps only the last 30 backups
- Shows file sizes
- Validates container is running

### List available backups

```bash
ls -lh ./backups/postgres/
```

### Restore from a backup

```bash
./scripts/restore-db.sh ./backups/postgres/inventory_backup_20240101_120000.sql.gz
```

The script will:
- Ask for confirmation
- Decompress the backup
- Restore to the running PostgreSQL container
- Verify success

**⚠️ WARNING**: Restore will OVERWRITE the current database!

## Disaster Recovery Procedure

Complete server rebuild while preserving all data:

### Step 1: Prepare the new environment

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Clone repository
git clone <your-repo-url> inventory-app
cd inventory-app
```

### Step 2: Restore from backup

Copy the backup file to the server:
```bash
scp ./backups/postgres/inventory_backup_*.sql.gz user@newserver:/tmp/
```

Or download from backup storage (S3, Google Drive, etc.).

### Step 3: Start PostgreSQL

```bash
# Create .env with previous values
cp .env.example .env
nano .env  # Use SAME credentials as before

# Start PostgreSQL only
docker compose up -d postgres
```

Wait for PostgreSQL to be healthy (max 50 seconds):
```bash
docker compose logs postgres  # Look for "database system is ready to accept connections"
```

### Step 4: Restore the database

```bash
./scripts/restore-db.sh /tmp/inventory_backup_20240101_120000.sql.gz
```

### Step 5: Start the application

```bash
docker compose up -d inventory-app
```

### Step 6: Verify data

```bash
# Check logs
docker compose logs inventory-app

# Access application
# http://your-server:5000
```

**Expected result**: All inventory data is restored exactly as it was.

## Deployment Updates

### Update the application code

1. Update your code in the repository
2. Rebuild and restart:

```bash
docker compose up -d --build inventory-app
```

This is **SAFE** because:
- PostgreSQL container is not recreated
- Database volume is not touched
- Only the app container is rebuilt
- Connection to PostgreSQL is re-established

### Update Docker images

```bash
# Pull latest images
docker compose pull

# Restart services
docker compose up -d
```

### Database schema changes

1. Make your database schema changes via code/migrations
2. Rebuild app:

```bash
docker compose up -d --build inventory-app
```

The application will migrate the schema on startup (if using Alembic migrations).

## Important: Safe vs Destructive Commands

### ✅ SAFE Commands (Application only)

These commands are safe and preserve all database data:

```bash
# Rebuild and restart app container
docker compose up -d --build inventory-app

# Stop app (database keeps running)
docker compose stop inventory-app

# Restart app
docker compose restart inventory-app

# Remove app container (volume persists!)
docker compose rm -f inventory-app

# View logs
docker compose logs

# Execute command in container
docker compose exec inventory-app bash
```

### ⚠️ POTENTIALLY DESTRUCTIVE

These commands might delete data if used incorrectly:

```bash
# DANGEROUS: Removes containers AND volumes
docker compose down -v
# ⚠️ This DELETES the PostgreSQL data volume!
# ⚠️ Only use for testing/development cleanup
```

### 🛑 DESTRUCTIVE

```bash
# DANGEROUS: Deletes named volume
docker volume rm inventory_postgres_data
# ⚠️ This PERMANENTLY DELETES all database data!
# ⚠️ Create a backup first!

# DANGEROUS: Removes all images
docker system prune -a
```

## Monitoring and Troubleshooting

### Check service status

```bash
docker compose ps
```

### Check service health

```bash
docker inspect $(docker compose ps -q postgres) | grep -A 5 '"Health"'
```

### View detailed logs

```bash
# All services
docker compose logs --tail=100

# Specific service
docker compose logs --tail=100 postgres
docker compose logs --tail=100 inventory-app

# Follow logs in real-time
docker compose logs -f
```

### Common issues

#### Application can't connect to database

```bash
# Check PostgreSQL is running and healthy
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres

# Verify credentials
docker compose exec postgres psql -U $DB_USER -d $DB_NAME -c "SELECT version();"
```

#### Application crashes after restart

```bash
# Check app logs
docker compose logs inventory-app

# Rebuild app
docker compose up -d --build inventory-app

# Check logs again
docker compose logs -f inventory-app
```

#### Database is out of disk space

```bash
# Check volume size
docker volume inspect inventory_postgres_data

# Check disk usage
docker exec inventory_postgres du -sh /var/lib/postgresql/data

# Clean up old backups
rm ./backups/postgres/inventory_backup_*.sql.gz (except latest)
```

### Test data persistence

This test verifies that data survives container recreation:

```bash
# 1. Add test data via web UI or API
# Or use curl:
curl -X POST http://localhost:5000/api/shops \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Shop","location":"Test Location"}'

# 2. Verify data exists
docker compose exec postgres psql -U $DB_USER -d $DB_NAME -c "SELECT * FROM shops;"

# 3. Stop and remove app container
docker compose down inventory-app

# 4. Verify database still has data
docker compose ps postgres  # Should still be running

# 5. Recreate app container
docker compose up -d inventory-app

# 6. Verify data is still there
docker compose exec postgres psql -U $DB_USER -d $DB_NAME -c "SELECT * FROM shops;"

# Result: All data should be intact!
```

## Environment Variables

All sensitive configuration is in `.env` (gitignored):

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| DB_HOST | PostgreSQL hostname | postgres | No (for Docker) |
| DB_PORT | PostgreSQL port | 5432 | No |
| DB_NAME | Database name | inventory | No |
| DB_USER | Database user | inventory_app | No |
| DB_PASSWORD | Database password | - | **YES** |
| FLASK_ENV | Flask environment | production | No |
| FLASK_SECRET | Flask session secret | - | **YES** |
| INVENTORY_USER | Admin username | admin | No |
| INVENTORY_PASS | Admin password | admin | No |
| APP_PORT | Application port | 5000 | No |

## Security Best Practices

1. ✅ Use strong passwords for DB_PASSWORD and INVENTORY_PASS
2. ✅ Generate a random FLASK_SECRET (min 32 characters)
3. ✅ Never commit `.env` to git (add to `.gitignore`)
4. ✅ Rotate credentials regularly
5. ✅ Use HTTPS in production (add reverse proxy/load balancer)
6. ✅ Restrict container port access with firewall
7. ✅ Backup database regularly and test restoration
8. ✅ Monitor logs for suspicious activity
9. ✅ Keep Docker images updated
10. ✅ Run containers as non-root user (already configured)

## File Structure

```
inventory-app/
├── app.py                      # Flask application
├── database.py                 # Database utilities
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Application image definition
├── docker-compose.yml          # Service orchestration
├── init-db.sql                 # PostgreSQL initialization
├── .env.example                # Environment template
├── .gitignore                  # Git ignore rules
├── scripts/
│   ├── backup-db.sh           # Backup script
│   └── restore-db.sh          # Restore script
├── templates/                  # HTML templates
├── static/                     # Static files
├── backups/postgres/           # Database backups (gitignored)
│   └── inventory_backup_*.sql.gz
└── DEPLOYMENT.md              # This file
```

## Advanced Topics

### Custom PostgreSQL configuration

Edit `docker-compose.yml` to add PostgreSQL parameters:

```yaml
postgres:
  environment:
    POSTGRES_INITDB_ARGS: "-c max_connections=200 -c shared_buffers=256MB"
```

### Volume driver options

To use different volume drivers (e.g., NFS):

```yaml
volumes:
  inventory_postgres_data:
    driver: nfs
    driver_opts:
      addr: "192.168.1.100"
      path: "/mnt/postgres-data"
```

### Multi-node deployment

For production multi-node Docker Swarm:

1. Convert compose file to stack
2. Use secrets for sensitive data
3. Deploy with `docker stack deploy`

### Automated backups with cron

Add to crontab:
```bash
# Run backup daily at 2 AM
0 2 * * * cd /path/to/inventory-app && ./scripts/backup-db.sh
```

## Support and Debugging

### Docker Compose reference
https://docs.docker.com/compose/compose-file/

### PostgreSQL documentation
https://www.postgresql.org/docs/

### Flask documentation
https://flask.palletsprojects.com/

### Enable debug logging

In `.env`:
```
FLASK_ENV=development
```

Then restart:
```bash
docker compose up -d --build inventory-app
docker compose logs -f inventory-app
```

---

**Last Updated**: 2024  
**Version**: 1.0  
**Status**: Production Ready
