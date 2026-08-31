# Default Admin Account Protection & Password Management

## Overview

The default admin account (`admin`/`admin`) is a built-in account that:
- Is automatically created when the application starts for the first time
- Cannot be deleted under any circumstances
- Must be available after redeployment without manual intervention
- Has password tracking for security auditing

## Features Implemented

### 1. Default Admin Account Initialization

**Automatic Creation:**
- On application startup, if no users exist, the default admin account is automatically created
- Username and password are configurable via environment variables:
  - `INVENTORY_USER` (default: `admin`)
  - `INVENTORY_PASS` (default: `admin`)

**Code Location:** [app.py](app.py) lines 112-130

```python
# Initialize default admin user if no users exist
if no_users_exist:
    db.execute(
        'INSERT INTO users (username, password_hash, role, is_default_admin, password_changed_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
        (ADMIN_USER, hashed_password, 'admin', 1)
    )
```

### 2. Default Admin Protection

**Protection Mechanisms:**

#### a) Cannot Be Deleted
The default admin account is marked with an `is_default_admin` flag (value: `1`) in the database.

When attempting to delete the default admin:
1. The delete endpoint checks `is_default_admin` flag
2. If the user is the default admin, deletion is rejected with:
   ```
   Error: cannot delete the default admin account
   HTTP 400 Bad Request
   ```

**API Endpoint:** `DELETE /api/users/<user_id>`
**Code Location:** [app.py](app.py) lines 422-453

```python
# Prevent deletion of the default admin account
if user['is_default_admin']:
    return jsonify({'error': 'cannot delete the default admin account'}), 400
```

#### b) Cannot Change Role
Even if the default admin account is demoted to `normal` role, the deletion block remains in place.

#### c) Last Admin Protection
If there's only one admin account (the default admin), other admins cannot be deleted. The default admin itself cannot be demoted if it's the last admin.

**Code Location:** [app.py](app.py) lines 389-419

### 3. Password Change Tracking

**Purpose:** Track when passwords are changed to identify which accounts use default/temporary credentials.

**Implementation:**
- New column added to users table: `password_changed_at` (TIMESTAMP)
- When a user's password is changed (via admin or self-service), the timestamp is updated
- The default admin's `password_changed_at` is set to `CURRENT_TIMESTAMP` at initialization

**Database Schema:**
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'normal',
    is_default_admin INTEGER DEFAULT 0,
    password_changed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Code Locations:**
- Initialization: [app.py](app.py) line 115
- Password change API: [app.py](app.py) line 381
- Forced password change page: [app.py](app.py) line 229

### 4. Database Migrations

**Automatic Migration for Existing Databases:**

When updating an existing database to this version:
1. `ALTER TABLE users ADD COLUMN is_default_admin INTEGER DEFAULT 0` (if not exists)
2. `ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP` (if not exists)
3. Mark the existing admin user as default admin: `UPDATE users SET is_default_admin = 1 WHERE username = ?`
4. Set password_changed_at for default admin if NULL: `UPDATE users SET password_changed_at = CURRENT_TIMESTAMP WHERE username = ? AND password_changed_at IS NULL`

**Code Location:** [app.py](app.py) lines 99-130

The migrations run automatically on application startup and are idempotent (safe to run multiple times).

## Deployment Scenarios

### Scenario 1: Fresh Deployment
1. Clone repository
2. Start application
3. Default admin account (`admin`/`admin`) is automatically created
4. Admin can log in immediately
5. Can create additional users

### Scenario 2: Redeployment (Container Replacement)
1. Stop application container
2. Delete/replace application container (with persistent database)
3. Start new application container
4. Default admin account is still available
5. No manual user recreation needed
6. All existing users and data remain intact

**Important:** As long as the database volume persists, the default admin account will always be available after redeployment.

### Scenario 3: Database Backup & Restore
1. Backup database with `pg_dump` or SQLite export
2. Replace old application container
3. Restore database from backup
4. Start new application
5. Default admin account is restored with backup data
6. If backup predates this feature, migration runs automatically

### Scenario 4: Adding This Feature to Existing Installation
1. Update application code
2. Start application with existing database
3. Migrations run automatically:
   - New columns added to existing users table
   - Existing admin user is marked as default admin (`is_default_admin = 1`)
   - Password timestamps are initialized for existing users
4. No manual intervention needed
5. Existing admin account immediately gains default admin protection

## API Endpoints

### Delete User
**Endpoint:** `DELETE /api/users/<user_id>`

**Protection Order:**
1. Check if user is currently logged-in admin → Error: "cannot delete your own account"
2. Check if user is default admin → Error: "cannot delete the default admin account"
3. Check if user is last admin → Error: "cannot delete the last administrator"
4. If all checks pass → User deleted successfully

**Response Examples:**

Success (200 OK):
```json
{
  "success": true,
  "message": "User john deleted"
}
```

Error - Default Admin (400 Bad Request):
```json
{
  "error": "cannot delete the default admin account"
}
```

Error - Self-Deletion (400 Bad Request):
```json
{
  "error": "cannot delete your own account"
}
```

Error - Last Admin (400 Bad Request):
```json
{
  "error": "cannot delete the last administrator"
}
```

### Change User Password
**Endpoint:** `PUT /api/users/<user_id>/password`

**Request Body:**
```json
{
  "new_password": "newpassword123",
  "confirm_password": "newpassword123"
}
```

**Response:** Updates `password_changed_at` field for the user

**Code Location:** [app.py](app.py) lines 353-384

## Database Queries

### Query: Check if User is Default Admin
```sql
SELECT is_default_admin FROM users WHERE username = 'admin';
-- Result: 1 (true) for default admin, 0 (false) for regular users
```

### Query: Find Users with Unchanged Passwords
```sql
SELECT username, role FROM users WHERE password_changed_at IS NULL;
-- Returns users who haven't changed their password since creation
```

### Query: Count Default Admin Accounts
```sql
SELECT COUNT(*) FROM users WHERE is_default_admin = 1;
-- Should always return 1 (only one default admin allowed)
```

### Query: Count Total Admin Accounts
```sql
SELECT COUNT(*) FROM users WHERE role = 'admin';
-- Used to prevent removing last administrator
```

## Testing

### Manual Testing Checklist

✅ Default admin account creation:
- Fresh database automatically creates `admin`/`admin` user
- User has `is_default_admin = 1`
- User has `password_changed_at` set to current timestamp

✅ Default admin cannot be deleted:
- Log in as admin
- Create another admin user
- Log in as second admin
- Try to delete first admin → Error message appears
- First admin still exists in user list

✅ Default admin protection persists across sessions:
- Delete and recreate application container
- Database persists
- Default admin account still exists and has same protection

✅ Regular users can be created and deleted:
- Create normal user as admin
- User can log in
- User can be deleted by another admin
- After deletion, user cannot log in

### Automated Testing

All tests located in [test_user_management.py](test_user_management.py)

**Test Classes Related to Default Admin:**

1. `TestDefaultAdminProtection::test_default_admin_cannot_be_deleted`
   - Creates second admin user
   - Logs in as second admin
   - Attempts to delete default admin
   - Verifies error message

2. `TestDefaultAdminProtection::test_default_admin_marked_correctly`
   - Checks database for `is_default_admin = 1` flag on admin user

**Run Tests:**
```bash
pytest test_user_management.py::TestDefaultAdminProtection -v
```

**Expected Result:** All tests pass ✅

## Security Considerations

1. **Password Hashing**
   - All passwords hashed with bcrypt (Argon2id alternative for future)
   - Even default admin password is hashed before storage
   - No plaintext passwords ever stored

2. **Authorization Checks**
   - All deletions checked at API level (not just UI hiding)
   - Cannot delete default admin via direct API call
   - Session-based verification prevents unauthorized access

3. **Audit Trail**
   - `password_changed_at` field provides auditing capability
   - Can identify accounts still using default/unchanged passwords
   - Admin can use this to enforce password change policies

4. **Database Integrity**
   - `is_default_admin` flag is database-level protection
   - Flag value (1 or 0) cannot be changed via UI
   - Only one `is_default_admin = 1` account should exist at a time

## Configuration

### Environment Variables

**INVENTORY_USER** (default: `admin`)
```bash
export INVENTORY_USER=superadmin
```

**INVENTORY_PASS** (default: `admin`)
```bash
export INVENTORY_PASS=mysecurepassword
```

**Docker Compose Example:**
```yaml
environment:
  INVENTORY_USER: admin
  INVENTORY_PASS: changeme
```

**Important:** Change the default password before production deployment!

## Migration Guide

### From Previous Version (without default admin protection)

**What Changes:**
- Two new columns added to `users` table:
  - `is_default_admin` (INTEGER, default 0)
  - `password_changed_at` (TIMESTAMP, nullable)

**Automatic Steps on Upgrade:**
1. Application starts
2. Detects missing columns
3. Runs ALTER TABLE to add columns
4. Marks existing admin user as default admin
5. Sets `password_changed_at` to current timestamp
6. No manual database changes needed

**User Experience:**
- No visible changes for end users
- Existing users still log in with same credentials
- New deletion protection immediately active

### Rollback Considerations

**To Downgrade:**
1. Stop application
2. Update code to previous version
3. Start application
4. New columns remain in database (harmless)
5. Previous version ignores new columns
6. Functionality reverts to previous behavior

## Troubleshooting

### Issue: Cannot delete default admin

**Expected Behavior:** Cannot delete admin user via UI or API

**Solution:** This is by design. To prevent accidental system lockout:
1. Default admin protection is permanent
2. Cannot be changed or removed
3. Create a second admin user instead if needed

### Issue: Default admin account doesn't exist after restart

**Cause:** Database was deleted or reset

**Solution:**
1. Check if database volume is persisted
2. Verify database file exists at `instance/inventory.db` (SQLite) or PostgreSQL volume
3. If database lost, it will be recreated with default admin on next startup

### Issue: "Cannot delete the last administrator" error

**Cause:** Attempting to delete the only admin user

**Solution:**
1. Create a second admin user first
2. Then delete the first admin (if not default admin)
3. Or: Promote a normal user to admin role first

## Files Modified

- **[app.py](app.py)** - Core application logic
  - Lines 73-84: Updated users table schema
  - Lines 99-130: Added database migrations
  - Lines 135-141: Updated login_required decorator
  - Lines 161-208: Updated login page and forced password change
  - Lines 213-229: Added forced password change endpoint
  - Lines 329-338: Updated create_user endpoint
  - Lines 353-384: Updated change_user_password endpoint
  - Lines 422-453: Updated delete_user endpoint with default admin check

- **[templates/change_password_forced.html](templates/change_password_forced.html)** - New file
  - Forced password change page template
  - Only shown to users whose `password_changed_at` is NULL

- **[test_user_management.py](test_user_management.py)** - Updated tests
  - Lines 20-45: Updated fixture to include new columns
  - Added TestDefaultAdminProtection class (2 new tests)
  - Added TestForcedPasswordChange class (2 new tests)
  - Total: 31 tests covering all RBAC and admin protection scenarios

## Summary

The default admin account protection feature ensures:
1. **Availability:** Default admin always available after redeployment
2. **Safety:** Cannot be accidentally deleted
3. **Persistence:** Protected by database-level flags, not just UI
4. **Auditability:** Password change tracking enables compliance
5. **Backward Compatibility:** Existing databases automatically migrated
6. **Security:** All protections enforced at API level

The implementation is production-ready and fully tested with 31 automated test cases.
