# Backup & Restore - Quick Reference

## What It Does
- Admins can create downloadable backups of the entire database
- Admins can restore from previously downloaded backups
- Complete disaster recovery without original Docker/volumes/installations

## Quick Start

### Create a Backup
1. Login as admin
2. Click **Backup & Restore** tile on home page
3. Click **Create Backup & Download**
4. File automatically downloads to your computer as `app-backup-YYYY-MM-DD-HHMM.zip`

### Restore a Backup
1. Login as admin
2. Click **Backup & Restore** tile
3. Click **Select Backup File**
4. Choose your backup ZIP file
5. Review the metadata (optional)
6. Click **Restore Database**
7. Confirm the warning dialog
8. Data is restored, application reloads

## API Endpoints

| Endpoint | Method | Access | Purpose |
|----------|--------|--------|---------|
| `/api/backup/create` | POST | Admin | Create and download backup |
| `/api/backup/restore` | POST | Admin | Upload and restore backup |
| `/api/backup/info` | POST | Admin | Get backup file information |
| `/backup-restore` | GET | Admin | UI page for backup operations |

## Access Control
- ✅ **Admin:** Full access to all backup/restore features
- ❌ **Normal Users:** Cannot access backup/restore page or APIs (get HTTP 403)
- ❌ **Unauthenticated:** Redirected to login

## Backup File Format
- **File Type:** ZIP archive
- **Filename:** `app-backup-2026-08-31-1600.zip`
- **Contents:**
  - `BACKUP_INFO.json` - Metadata (format version, app version, schema version, created timestamp)
  - `database.json` - All database tables exported as JSON

## Backup Data Includes
- Users and roles
- Shops and locations
- Products and product lists
- Inventory items and quantities
- All relationships and configurations

## Security
- Authorization enforced at API level (not just UI)
- Non-admin requests: HTTP 403 Forbidden
- Passwords stored as bcrypt hashes in backup
- Uploaded backups validated before restoration
- Temporary files auto-cleaned after backup generation

## Storage Recommendations
**Local Computer:** Primary storage location
- Download backups to your computer/workstation
- Create dated backup folder for organization

**Cloud Storage (Optional):** Copy backups to:
- Google Drive
- OneDrive
- AWS S3 / Azure Blob Storage
- Dropbox or similar

**Retention:** Keep multiple backups (e.g., last 4 weeks)

## Disaster Recovery in 5 Steps

```
1. Reinstall application
   └─ docker compose up -d

2. Login as admin
   └─ username: admin, password: admin

3. Go to Backup & Restore page
   └─ Click Backup & Restore tile

4. Upload backup
   └─ Select Backup File → Choose ZIP → Restore Database

5. Confirm restoration
   └─ Click "Yes, Restore Database" in warning dialog
```

## Limitations
- ❌ No automatic/scheduled backups
- ❌ No server-side backup history
- ❌ No encryption (future enhancement)
- ❌ Full export (not incremental)
- ❌ Requires manual user action

## Testing Backup/Restore
```bash
# Run automated tests
pytest test_user_management.py::TestBackupRestore -v

# Result: 14/14 tests passing ✅
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Can't access Backup & Restore page | Not admin | Login as admin user |
| "Backup creation failed" | Database error | Check app logs, verify DB connection |
| "Invalid backup" error | Corrupted file | Re-download backup file and try again |
| Restoration hangs | Large backup file | Wait longer or check browser console |
| Missing data after restore | Wrong backup file | Verify you selected the correct backup |

## Key Facts
- **Format Version:** 1
- **Database Schema Version:** 5
- **Portable:** Works on any OS/Docker/filesystem
- **No Server Storage:** Backups exist only during download/restore
- **Complete:** All application data included
- **Validated:** Format and content verification before restore
- **Safe:** Non-destructive if validation fails

---

**For detailed information:** See [BACKUP_RESTORE_FEATURE.md](BACKUP_RESTORE_FEATURE.md)
