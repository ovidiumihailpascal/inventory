# Docker Deployment Test Procedure
# This procedure validates that the application container is disposable and data persists

## Prerequisites
- Docker Compose running
- Application and PostgreSQL containers running
- PostgreSQL accessible from host

## Test 1: Verify Initial Setup

```bash
# 1.1 Check all services are running
docker compose ps
# Expected output: inventory-app and postgres both RUNNING

# 1.2 Verify PostgreSQL data volume exists
docker volume ls | grep inventory_postgres_data
# Expected: inventory_postgres_data listed

# 1.3 Connect to application
curl http://localhost:5000/login
# Expected: Login page loads

# 1.4 Verify database connectivity
docker compose exec postgres psql -U inventory_app inventory -c "SELECT COUNT(*) FROM shops;"
# Expected: Returns count (example: 1 shop)
```

## Test 2: Create Test Data

```bash
# 2.1 Log in to application (use default or configured credentials)
# Navigate to http://localhost:5000/login
# Enter credentials and create test data:
# - Create a shop (e.g., "Test Store")
# - Create a product (e.g., "Ribeye Steak", 25.99 RON)
# - Add inventory item (e.g., 10 units)

# 2.2 Verify data in database
docker compose exec postgres psql -U inventory_app inventory -c "
SELECT 'shops' as table_name, COUNT(*) as count FROM shops
UNION ALL
SELECT 'items', COUNT(*) FROM items
UNION ALL
SELECT 'product_lists', COUNT(*) FROM product_lists
UNION ALL
SELECT 'list_items', COUNT(*) FROM list_items;
"

# Expected output:
# table_name     | count
# ---------------------
# shops          |     1
# items          |     1
# product_lists  |     1
# list_items     |     1
```

## Test 3: Backup Current Data

```bash
# 3.1 Create a backup before destruction test
./scripts/backup-postgres.sh  # Linux/macOS
# or
scripts\backup-postgres.bat   # Windows

# 3.2 Verify backup file exists
ls -lh backups/postgres/
# Expected: Recent backup file with >1KB size
```

## Test 4: THE CRITICAL TEST - Container Destruction and Recreation

This test verifies the core requirement: **Application container is disposable, data is persistent**

```bash
# 4.1 Document current data
echo "=== BEFORE DESTRUCTION ==="
docker compose exec postgres psql -U inventory_app inventory -c "
SELECT 'Shops:' as info;
SELECT id, name, location FROM shops;
SELECT '';
SELECT 'Inventory:' as info;
SELECT id, name, shop_id, qty, cut_type FROM items;
SELECT '';
SELECT 'Products:' as info;
SELECT id, item_name, cut_type, price FROM list_items;
" > /tmp/data_before.txt

cat /tmp/data_before.txt

# 4.2 STOP the application container ONLY
echo "Stopping application container..."
docker compose stop inventory-app

# 4.3 Verify app is stopped, postgres still running
docker compose ps
# Expected: 
# inventory-app  | Stopped
# postgres       | Running

# 4.4 Verify data still exists in postgres
docker compose exec postgres psql -U inventory_app inventory -c "SELECT COUNT(*) FROM shops;"
# Expected: Count returned (data still there!)

# 4.5 REMOVE the application container
echo "Removing application container..."
docker compose rm -f inventory-app

# 4.6 Verify container is gone
docker compose ps
# Expected: Only postgres listed

# 4.7 Verify data STILL exists in postgres volume
docker compose exec postgres psql -U inventory_app inventory -c "SELECT COUNT(*) FROM shops;"
# Expected: Count returned (data still there!)

# 4.8 REBUILD the application image
echo "Rebuilding application image..."
docker compose build inventory-app

# 4.9 CREATE NEW application container
echo "Creating new application container..."
docker compose up -d inventory-app

# 4.10 Wait for application to start
echo "Waiting for application to be ready..."
sleep 10

docker compose logs inventory-app
# Expected: Application started, database connected

# 4.11 Verify application is running
docker compose ps
# Expected: Both inventory-app and postgres RUNNING

# 4.12 VERIFY ALL DATA IS INTACT
echo ""
echo "=== AFTER RECREATION ==="
docker compose exec postgres psql -U inventory_app inventory -c "
SELECT 'Shops:' as info;
SELECT id, name, location FROM shops;
SELECT '';
SELECT 'Inventory:' as info;
SELECT id, name, shop_id, qty, cut_type FROM items;
SELECT '';
SELECT 'Products:' as info;
SELECT id, item_name, cut_type, price FROM list_items;
" > /tmp/data_after.txt

cat /tmp/data_after.txt

# 4.13 Compare before and after
echo ""
echo "=== DATA COMPARISON ==="
diff /tmp/data_before.txt /tmp/data_after.txt

if [ $? -eq 0 ]; then
  echo "✅ SUCCESS: Data is IDENTICAL before and after container recreation"
else
  echo "❌ FAILURE: Data changed during container recreation"
  exit 1
fi
```

## Test 5: Verify Application Idempotency

Test that the application doesn't create duplicate records on restart:

```bash
# 5.1 Get current record counts
docker compose exec postgres psql -U inventory_app inventory -c "
SELECT 'shops', COUNT(*) FROM shops
UNION ALL
SELECT 'items', COUNT(*) FROM items
UNION ALL
SELECT 'product_lists', COUNT(*) FROM product_lists
UNION ALL
SELECT 'list_items', COUNT(*) FROM list_items;
" > /tmp/counts_before_restart.txt

# 5.2 Restart application
docker compose restart inventory-app

# 5.3 Wait for it to restart
sleep 5

# 5.4 Get counts again
docker compose exec postgres psql -U inventory_app inventory -c "
SELECT 'shops', COUNT(*) FROM shops
UNION ALL
SELECT 'items', COUNT(*) FROM items
UNION ALL
SELECT 'product_lists', COUNT(*) FROM product_lists
UNION ALL
SELECT 'list_items', COUNT(*) FROM list_items;
" > /tmp/counts_after_restart.txt

# 5.5 Verify counts are identical
diff /tmp/counts_before_restart.txt /tmp/counts_after_restart.txt

if [ $? -eq 0 ]; then
  echo "✅ SUCCESS: No duplicate records created on restart (idempotent)"
else
  echo "❌ FAILURE: Duplicate records were created"
  exit 1
fi
```

## Test 6: Verify Web Interface Works

```bash
# 6.1 Access login page
curl -s http://localhost:5000/login | grep -q "login" && echo "✅ Login page loads"

# 6.2 Access home page (may require auth in real scenario)
curl -s http://localhost:5000/ | grep -q "html" && echo "✅ Application responds"

# 6.3 Access API
curl -s http://localhost:5000/api/shops | python -m json.tool > /dev/null && echo "✅ API returns valid JSON"
```

## Test 7: Verify Database Backups

```bash
# 7.1 Restore from backup in new location
docker run -d \
  --name test-postgres \
  -e POSTGRES_DB=inventory_test \
  -e POSTGRES_USER=inventory_app \
  -e POSTGRES_PASSWORD=testpass \
  postgres:15-alpine

sleep 5

# 7.2 Create the schema in test database
docker exec test-postgres psql -U inventory_app inventory_test -f init-db.sql

# 7.3 Restore the backup
docker exec test-postgres psql -U inventory_app inventory_test < backups/postgres/inventory_*.sql

# 7.4 Verify data exists
docker exec test-postgres psql -U inventory_app inventory_test -c "SELECT COUNT(*) FROM shops;"

# 7.5 Clean up test container
docker rm -f test-postgres

# ✅ If we got here without errors, backups are restorable
```

## Test 8: Verify Volume Persistence

```bash
# 8.1 Check volume actual disk usage
docker volume inspect inventory_inventory_postgres_data

# 8.2 Verify volume contains data files
docker run --rm -v inventory_inventory_postgres_data:/data busybox \
  ls -lh /data/

# Expected: Should see postgresql data files and directories
```

## Success Criteria

All tests pass if:

✅ **Test 1** - Services start correctly  
✅ **Test 2** - Data can be created and queried  
✅ **Test 3** - Backups can be created  
✅ **Test 4** - Application container can be destroyed and recreated WITHOUT DATA LOSS  
✅ **Test 5** - Application doesn't create duplicates on restart (idempotent)  
✅ **Test 6** - Web interface works after recreation  
✅ **Test 7** - Backups can be restored  
✅ **Test 8** - Volume persists data  

**If all tests pass, the deployment meets all requirements:**
- ✅ Application is disposable
- ✅ PostgreSQL data is persistent  
- ✅ Backups work
- ✅ Disaster recovery is possible
- ✅ Application is idempotent

## Failure Recovery

If any test fails:

1. Check error message
2. Review DOCKER_DEPLOYMENT.md troubleshooting section
3. Inspect logs: `docker compose logs`
4. Restore from backup if needed: `./scripts/restore-postgres.sh`
5. Re-run test

## Summary Commands

Quick reference for the critical test (Test 4):

```bash
# Before destruction
docker compose ps
docker compose exec postgres psql -U inventory_app inventory -c "SELECT COUNT(*) FROM shops;"

# Destruction
docker compose stop inventory-app
docker compose rm -f inventory-app
docker compose build inventory-app
docker compose up -d inventory-app
sleep 10

# After recreation
docker compose ps
docker compose exec postgres psql -U inventory_app inventory -c "SELECT COUNT(*) FROM shops;"

# If both counts are the same: ✅ SUCCESS
```

---

**Last Updated:** 2024-01-15
**Status:** Production Ready
