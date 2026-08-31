# Docker Deployment Quick Start

## Why Docker?

This deployment provides:
- ✅ **Persistent Data**: Database stored in Docker volumes, survives container recreation
- ✅ **Easy Deployment**: Single `docker compose up` command
- ✅ **Backup & Restore**: Automated backup scripts included
- ✅ **Scalability**: Can run multiple replicas of the app
- ✅ **Disaster Recovery**: Complete recovery procedures documented

## Quick Start (5 minutes)

### 1. Prerequisites
```bash
# Install Docker Desktop (includes Docker Compose)
# https://www.docker.com/products/docker-desktop/

# Verify installation
docker --version
docker compose --version
```

### 2. Clone and Setup
```bash
cd /path/to/inventory

# Copy environment template
cp .env.example .env

# Edit .env and change passwords
nano .env
# Change: DB_PASSWORD, FLASK_SECRET, INVENTORY_PASS
```

### 3. Start the Application
```bash
# Start services (this will take 1-2 minutes first time)
docker compose up -d

# Wait for startup
sleep 30

# Check status
docker compose ps
# Expected: Both services should show "running"

# View logs
docker compose logs -f inventory-app
# Wait for: "Application started on 0.0.0.0:5000"
```

### 4. Access the Application
```bash
# Open in browser
http://localhost:5000

# Login with credentials from .env
# Username: admin (or INVENTORY_USER)
# Password: (or INVENTORY_PASS)
```

### 5. Create Test Data
- Click "Product Lists" → Add "Ribeye Steak" at 25.99 RON
- Click "Shops" → Add "Main Store" in Bucharest  
- Click "Inventory" → Add 10 units of Steak to Main Store
- Verify data appears in the application

## Verify Data Persistence (Critical Test!)

This proves your data is safe:

```bash
# 1. Note the current data count
docker compose exec postgres psql -U inventory_app inventory -c "SELECT COUNT(*) FROM items;"
# Example output: 1

# 2. Destroy the application container
docker compose stop inventory-app
docker compose rm -f inventory-app

# 3. Verify data still in database
docker compose exec postgres psql -U inventory_app inventory -c "SELECT COUNT(*) FROM items;"
# Same count as before! Data is safe!

# 4. Recreate and restart application
docker compose up -d inventory-app

# 5. Login and verify data is still there
# http://localhost:5000
# All products and inventory still present!

# ✅ This proves application is disposable, data persists!
```

## Backup Your Data

```bash
# Linux/macOS
./scripts/backup-postgres.sh

# Windows
scripts\backup-postgres.bat

# Backups created in: ./backups/postgres/
# Keep these safe!
```

## Common Commands

```bash
# View logs
docker compose logs inventory-app
docker compose logs postgres

# Restart
docker compose restart

# Stop (data preserved)
docker compose stop

# Start after stopping
docker compose start

# Stop and remove containers (but keep data)
docker compose down

# Remove everything including data (⚠️ data loss!)
docker compose down -v

# Rebuild app after code changes
docker compose up -d --build inventory-app

# Access database directly
docker compose exec postgres psql -U inventory_app inventory
```

## Troubleshooting

### Issue: "Cannot connect to PostgreSQL"
```bash
# Check if PostgreSQL is running and healthy
docker compose logs postgres
# Should see: "database system is ready to accept connections"

# Wait 30 seconds and try again
sleep 30
docker compose exec postgres psql -U inventory_app inventory -c "SELECT 1;"
```

### Issue: "Application not accessible at localhost:5000"
```bash
# Check if application started
docker compose logs inventory-app

# Verify port 5000 is not in use
netstat -an | grep 5000  # Linux/Mac
netstat -ano | grep 5000  # Windows

# Restart
docker compose restart inventory-app
sleep 10
curl http://localhost:5000
```

### Issue: "Forgot database password"
```bash
# Need to rebuild with new password in .env
docker compose down
# Edit .env with new DB_PASSWORD
nano .env
docker compose up -d
```

## Next Steps

- **For Production Deployment**: See [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
- **For Testing Procedures**: See [DOCKER_TEST.md](DOCKER_TEST.md)
- **For Backup & Recovery**: See [DOCKER_DEPLOYMENT.md#backup-and-recovery](DOCKER_DEPLOYMENT.md#backup-and-recovery)
- **For Monitoring**: See [DOCKER_DEPLOYMENT.md#production-checklist](DOCKER_DEPLOYMENT.md#production-checklist)

## Architecture

```
Your Computer (or Server)
    │
    ├── Application Container (Port 5000)
    │   └── Python Flask App
    │       └── Connects to...
    │
    └── PostgreSQL Container (Port 5432)
        └── Database
            └── Stores data in...
                └── Docker Volume (Persists on host disk)
```

- **Application** can be deleted/recreated without affecting data
- **Database Volume** persists even if containers are removed
- **Backups** stored in `./backups/postgres/` on your computer

## Important Notes

⚠️ **Never run**: `docker compose down -v`  
This deletes database volume and all data!

✅ **Always safe**: `docker compose down`  
This only removes containers, data persists in volumes.

✅ **Always safe**: `docker compose restart`  
This restarts containers, data unchanged.

---

For detailed documentation, see:
- [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md) - Complete deployment guide
- [DOCKER_TEST.md](DOCKER_TEST.md) - Testing procedures
- [.env.example](.env.example) - All configurable options

**Status**: Production Ready ✅
**Version**: 1.0
**Last Updated**: 2024-01-15
