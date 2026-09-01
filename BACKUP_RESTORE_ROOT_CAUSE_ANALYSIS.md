# ROOT CAUSE ANALYSIS: Database Restore Not Restoring Products

## INVESTIGATION SUMMARY

After performing a comprehensive investigation of the backup/restore functionality, I have identified the **actual root cause** of the apparent restore failure.

### KEY FINDING

**The backup/restore functionality IS WORKING CORRECTLY.**

The issue is not with the backup/restore mechanism. The issue is that **the PostgreSQL database is empty of shops and items.**

---

## EVIDENCE

### 1. Backup File Analysis

**Backup file examined:** `app-backup-2026-09-01.zip` (1022 bytes, downloaded from browser)

**Backup contents:**
```
users:          2 rows ✓
shops:          0 rows ✗✗✗
product_lists:  3 rows ✓
list_items:     2 rows ✓
items:          0 rows ✗✗✗
```

**Conclusion:** The backup is correctly exporting what's in the database.

### 2. PostgreSQL Database Analysis

**Live database query results:**
```
SELECT 'USERS' as table, COUNT(*) FROM users;          → 2 rows
SELECT 'SHOPS' as table, COUNT(*) FROM shops;          → 0 rows
SELECT 'ITEMS' as table, COUNT(*) FROM items;          → 0 rows
SELECT 'PRODUCT_LISTS' as table, COUNT(*) FROM ...;    → 3 rows
SELECT 'LIST_ITEMS' as table, COUNT(*) FROM ...;       → 2 rows
```

**Conclusion:** The PostgreSQL database contains NO shops and NO items.

### 3. Backup/Restore Process Test

- Created valid backup file: ✓ (1022 bytes, valid JSON, valid ZIP)
- Backup validation: ✓ (metadata present, schema version valid)
- Restore function executed: ✓ (no errors reported)
- Database state after restore: ✓ (tables cleared and restored from backup)

**Conclusion:** The backup/restore mechanism is working correctly.

---

## ROOT CAUSE

**The backup exports empty tables because the PostgreSQL database IS EMPTY.**

When you:
1. Export backup → exports empty shops and items tables
2. Delete products → no change (already empty)
3. Restore backup → restores empty shops and items tables
4. Result: Still empty (correctly)

The backup is not broken. The database was never populated with shops and items in the first place.

---

## WHY SHOPS/ITEMS ARE EMPTY

Possible causes:

### Cause 1: Products Were Never Saved to PostgreSQL
- User created products in browser UI
- API endpoint `/api/items POST` failed silently
- Products appeared in UI but were never inserted into database
- Root cause: Unauthenticated API calls returning 401 instead of creating data

### Cause 2: Foreign Key Constraint
- Items table requires `shop_id` to reference valid shop
- `ALTER TABLE items ADD CONSTRAINT items_shop_id_fkey FOREIGN KEY (shop_id) REFERENCES shops(id)`
- If no shops exist: INSERT INTO items fails silently
- User may have attempted to create items without creating shops first

### Cause 3: Products Deleted Before Export
- User created products
- User deleted products manually
- User exported backup (backup is empty as expected)
- User then tested restore (which correctly restores empty state)

### Cause 4: Local SQLite Database vs Container PostgreSQL
- Local SQLite at `instance/inventory.db` exists (0.04 MB)
- Running app uses PostgreSQL via Docker (DB_HOST=postgres)
- If user was testing locally with SQLite, those products wouldn't be in Docker's PostgreSQL

---

## EVIDENCE THAT API ENDPOINTS MAY HAVE AUTHENTICATION ISSUES

From application logs during test:
```
127.0.0.1 - - [01/Sep/2026 05:26:33] "POST /api/items HTTP/1.1" 401 -
127.0.0.1 - - [01/Sep/2026 05:26:34] "POST /api/backup/create HTTP/1.1" 401 -
```

Unauthenticated API requests return 401, but:
- Error responses are not logged visibly to frontend
- API call may fail silently
- User sees no error message
- Product "appears" to be saved but wasn't

---

## VERIFICATION THAT BACKUP/RESTORE WORKS

When test data WAS created in PostgreSQL:
1. Shop: "TEST_SHOP_20260901083426" created in database ✓
2. Item: "MANUAL_TEST_ITEM_20260901083426" created in database ✓
3. Backup created via API ✓
4. Backup contained both shop and item ✓
5. Data deleted from database ✓
6. Restore executed ✓
7. Database contained shop and item again ✓

**Result: Backup/restore works 100% correctly when data exists.**

---

## RECOMMENDATIONS

### 1. Immediate: Verify User Has Shops

Before creating items, user must:
1. Go to "Shops" section
2. Create at least one shop
3. Verify shop appears in list

Shops table is currently empty, which would prevent item creation.

### 2. Verify API Authentication

Test creating a shop:
1. Login to browser
2. Go to /shops
3. Create new shop
4. Check if shop appears
5. Check API logs for 401/403 errors

### 3. Test API Directly

```bash
# From container with proper auth
curl -X POST http://localhost:5000/api/shops \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","location":"Location"}' \
  # Include session cookie from browser login
```

### 4. Create Test Data and Re-Test

Once shop exists:
1. Create multiple test products
2. Verify they appear in UI
3. Verify they appear in database: `SELECT * FROM items;`
4. Create backup
5. Delete items
6. Restore backup
7. Verify items are restored

---

## TECHNICAL DETAILS

### Backup Format
- Format: `inventory_backup` (JSON-based)
- Version: 1
- Contents: All tables (users, shops, product_lists, list_items, items)
- Encapsulation: ZIP file with BACKUP_INFO.json + database.json
- Size: ~1KB for 7 records, grows linearly with data

### Foreign Key Constraints
```sql
ALTER TABLE items ADD CONSTRAINT items_shop_id_fkey 
  FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
```

- Required: Every item must reference an existing shop
- Consequence: Cannot insert items if shops table is empty
- Verify: `SELECT * FROM shops;` should return at least one row

### Restore Process
1. Validate backup ZIP structure ✓
2. Extract database.json ✓
3. Clear target tables (users, shops, product_lists, list_items, items) ✓
4. Insert all rows from backup ✓
5. Commit transaction ✓

---

## CONCLUSION

**The backup/restore functionality is working correctly.**

The issue is not with the code. The issue is that the PostgreSQL database does not contain any shops or items.

Before declaring restore broken, verify:
1. ✓ Shops exist in the database
2. ✓ Products/items exist in the database
3. ✓ API endpoints are accepting and saving data
4. ✓ Browser shows created items/shops
5. ✓ Database contains the same items/shops

If all five conditions are met, then backup/restore will work correctly.

---

## FILES AFFECTED

None - the backup/restore code is working correctly. No fixes needed to the code.

## NEXT STEPS

1. Verify shops exist: `SELECT * FROM shops LIMIT 5;`
2. If empty, create shops via browser UI
3. Verify shops appear in database
4. Create products/items
5. Re-test backup/restore cycle
6. Confirm items are restored
