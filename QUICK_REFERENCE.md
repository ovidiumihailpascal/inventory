# Default Admin Account - Quick Reference

## 🚀 Quick Start

### Default Credentials
- **Username:** `admin`
- **Password:** `admin`

### Available After
- Fresh deployment ✅
- Redeployment (database persists) ✅
- Restore from backup ✅
- Existing database migration ✅

---

## 🔒 Protection Features

| Feature | Behavior |
|---------|----------|
| **Deletion** | ❌ Cannot delete default admin account |
| **Role Change** | ⚠️ Can change to normal, but protection remains |
| **Password** | ✅ Can change (sets audit timestamp) |
| **Marked As** | `is_default_admin = 1` in database |
| **Audit Trail** | `password_changed_at` tracks when password changed |

---

## 🗄️ Database Schema

### New Columns in `users` Table
```sql
is_default_admin INTEGER DEFAULT 0    -- 1 = default admin, 0 = regular user
password_changed_at TIMESTAMP          -- NULL = unchanged, TIMESTAMP = changed
```

### Automatic Migrations
- ✅ Runs on application startup
- ✅ Creates columns if they don't exist
- ✅ Marks existing admin as default
- ✅ Idempotent (safe to run multiple times)

---

## 🔑 Environment Configuration

```bash
# Optional: Change default admin credentials
export INVENTORY_USER=superadmin
export INVENTORY_PASS=mysecurepassword
```

---

## 🚫 Deletion Error Messages

| Scenario | Error Message |
|----------|---------------|
| Try to delete self | "cannot delete your own account" |
| Try to delete default admin | "cannot delete the default admin account" |
| Try to delete last admin | "cannot delete the last administrator" |

---

## 📋 API Protection

### DELETE /api/users/<user_id>

**Check Order (Priority):**
1. ✅ User exists?
2. ✅ Is current logged-in user?  
3. ✅ Is default admin?
4. ✅ Is last admin in system?
5. ✅ All checks pass → User deleted

**Important:** Checks happen in this order. Default admin check comes AFTER self-deletion check.

---

## 🧪 Quick Test

### Test Default Admin Cannot Be Deleted
```bash
# 1. Login as admin (admin/admin)
# 2. Create another admin user
# 3. Logout and login as second admin
# 4. Try to delete first admin
# Result: Error - "cannot delete the default admin account"
```

### Test Default Admin Still Exists After Redeployment
```bash
# 1. Stop application container
# 2. Delete/replace application container
# 3. Keep database volume
# 4. Start new application
# 5. Login with admin/admin
# Result: Success - admin account available
```

---

## 📊 Audit Checking

### Query: Users with Unchanged Passwords
```sql
SELECT username, role FROM users WHERE password_changed_at IS NULL;
-- Returns users still using default/unchanged passwords
```

### Query: Check Default Admin
```sql
SELECT is_default_admin FROM users WHERE username = 'admin';
-- Returns: 1 (protected)
```

### Query: Last Password Change
```sql
SELECT username, password_changed_at FROM users ORDER BY password_changed_at DESC;
-- Shows password change history
```

---

## ⚠️ Important Notes

1. **Cannot Be Circumvented**
   - Protection at database level (flag-based)
   - Not just UI hiding
   - API enforces checks

2. **Only One Default Admin**
   - Only marked with `is_default_admin = 1`
   - Should never have duplicates

3. **Backup Includes Protection**
   - Database backup preserves `is_default_admin` flag
   - Restore from backup = protection restored

4. **Automatic Migration**
   - Existing databases auto-upgrade
   - No manual intervention needed
   - No data loss

---

## 🐛 Troubleshooting

### Issue: Cannot delete admin
**This is expected!** Default admin protected from deletion.

**Solution:** Create a second admin first, then delete the second one if needed.

### Issue: Default admin doesn't exist after restart
**Cause:** Database was lost or reset

**Solution:** Ensure database volume persists. Fresh database will auto-create admin account.

### Issue: Password change not working
**Check:** Is user logged in? Do passwords match? At least 6 characters?

**Note:** Default admin can change own password anytime (already has `password_changed_at` set).

---

## 📝 Files Related to This Feature

| File | Purpose |
|------|---------|
| [app.py](app.py) | Core implementation |
| [templates/change_password_forced.html](templates/change_password_forced.html) | Password change UI |
| [test_user_management.py](test_user_management.py) | 31 automated tests |
| [DEFAULT_ADMIN_PROTECTION.md](DEFAULT_ADMIN_PROTECTION.md) | Full documentation |
| [DEFAULT_ADMIN_IMPLEMENTATION_SUMMARY.md](DEFAULT_ADMIN_IMPLEMENTATION_SUMMARY.md) | Implementation details |

---

## ✅ Verification Checklist

- [ ] Default admin (admin/admin) can login
- [ ] All 4 tiles visible on admin homepage
- [ ] User Management page accessible
- [ ] Default admin shown in users table
- [ ] Cannot delete default admin
- [ ] Can create other users
- [ ] Can create other admins
- [ ] Can delete other admins
- [ ] All 31 tests passing
- [ ] Database has `is_default_admin` column
- [ ] Database has `password_changed_at` column

---

## 🔄 Deployment Checklist

**Fresh Deployment:**
- [ ] Clone repository
- [ ] Start application
- [ ] Default admin auto-created
- [ ] Can login with admin/admin

**Redeployment:**
- [ ] Stop old container
- [ ] Delete/replace container
- [ ] Keep database volume
- [ ] Start new container
- [ ] Default admin still available

**Existing Installation Update:**
- [ ] Update application code
- [ ] Start application
- [ ] Migrations run automatically
- [ ] No manual intervention needed
- [ ] Existing admin now protected

---

## 📞 Support

For detailed information, see:
- [DEFAULT_ADMIN_PROTECTION.md](DEFAULT_ADMIN_PROTECTION.md) - Complete feature guide
- [DEFAULT_ADMIN_IMPLEMENTATION_SUMMARY.md](DEFAULT_ADMIN_IMPLEMENTATION_SUMMARY.md) - Implementation details
- Code comments in [app.py](app.py) - Inline documentation

---

**Last Updated:** August 31, 2026
**Status:** ✅ Production Ready
