# User Management and Role-Based Access Control

## Overview

The inventory application now implements a complete user management system with role-based access control (RBAC). This document describes the feature, its architecture, and how to use it.

### Features

- **User Management**: Create, read, update, and delete users
- **Password Security**: Passwords are hashed using bcrypt with salt
- **Role-Based Access Control**: Two roles (`admin` and `normal`) with different permissions
- **Admin-Only Tile**: User Management tile appears only for admin users
- **Protected API Endpoints**: All user management endpoints require admin authentication
- **Last Admin Protection**: System prevents removal of the last administrator
- **Self-Deletion Protection**: Logged-in admins cannot delete their own account
- **Role Management**: Admins can assign roles between `admin` and `normal`
- **Password Management**: Admins can change any user's password

---

## User Roles

### Admin Role

An administrator can:

- Access the User Management page and tile on the home page
- View all existing users
- Create new users (both `normal` and `admin`)
- Change any user's password
- Change any user's role between `admin` and `normal`
- Delete any user (except self and the last remaining admin)
- Access all inventory features

### Normal Role (Default)

A normal user can:

- Log in and use the inventory application
- Access Inventory, Product Lists, and Shops features
- Cannot see the User Management tile on the home page
- Cannot access the User Management page (`/users`)
- Cannot call user management API endpoints
- Receives HTTP 401/403 if attempting to access protected endpoints

---

## Database Schema

The users table stores:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Constraints

- **username**: UNIQUE - no duplicate usernames allowed
- **role**: Must be exactly `'admin'` or `'normal'` (enforced by application)
- **password_hash**: Hashed using bcrypt (never plaintext)

---

## Default Admin User

On first application startup, a default admin user is automatically created if no users exist:

```
Username: admin
Password: admin
Role: admin
```

You can customize these defaults by setting environment variables:

```bash
export DEFAULT_ADMIN_USERNAME=myname
export DEFAULT_ADMIN_PASSWORD=mypassword
```

---

## Architecture

### Authentication Flow

1. User submits login form with username and password
2. Backend queries `users` table for matching username
3. `verify_password()` uses bcrypt to compare provided password with stored hash
4. On success, Flask session stores: `user`, `user_id`, `user_role`
5. Session is persistent across requests via Flask-Session

### Authorization Flow

Every protected endpoint checks:

1. Is the user authenticated? (check session)
2. Does the user have the required role? (check `user_role` in session)

Example:

```python
@admin_required
def api_users():
    # Only executes if user is both authenticated AND has admin role
    # Returns 401 if not authenticated
    # Returns 403 if authenticated but not admin
```

### Password Hashing

Passwords are hashed using **bcrypt**:

1. User provides plaintext password during registration or password change
2. `hash_password()` applies bcrypt salt and hashing
3. Hash is stored in database (never plaintext)
4. On login, `verify_password()` compares provided password with stored hash
5. Bcrypt automatically handles salt comparison

Bcrypt features:

- Salted hashing: each password has a unique salt
- Slow algorithm: resistant to brute force attacks
- Modern industry standard: resistant to rainbow tables

---

## User Management Page

### URL

`GET /users` (admin only)

### Access

- Only accessible to users with `admin` role
- Normal users are redirected with permission error message
- Non-authenticated users are redirected to login

### Page Layout

1. **Create New User** form:
   - Username field (must be unique)
   - Password field (minimum 6 characters)
   - Confirm Password field (must match password)
   - Role dropdown (Normal User or Administrator, defaults to Normal User)
   - Create button

2. **Existing Users** table:
   - Columns: Username, Role, Created Date, Actions
   - Action buttons for each user:
     - **Change Password**: Opens modal to set new password
     - **Change Role**: Opens modal to change role (with last-admin protection)
     - **Delete**: Opens confirmation modal to delete user (with protections)

### Modals

#### Change Password Modal

- Shows username (read-only)
- New password field (minimum 6 characters)
- Confirm new password field
- Password confirmation validation
- Change Password button

#### Change Role Modal

- Shows username (read-only)
- Shows current role (read-only)
- New role dropdown (Normal User or Administrator)
- Change Role button

#### Delete User Modal

- Confirms user wants to delete
- Shows warning: "This action cannot be undone"
- Delete User button
- Cancel button

---

## API Endpoints

All endpoints require authentication. Admin-only endpoints require the `admin` role.

### Authentication

Use Flask session. Example:

```python
@app.route('/api/users')
@login_required  # Already in session
@admin_required  # Must be admin
def list_users():
    ...
```

### Endpoints

#### `GET /api/users` (Admin only)

List all users.

**Response (200):**

```json
[
  {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "created_at": "2026-08-31T13:30:00"
  },
  {
    "id": 2,
    "username": "john",
    "role": "normal",
    "created_at": "2026-08-31T13:35:00"
  }
]
```

**Error (401):** Unauthenticated user

**Error (403):** Non-admin user

#### `POST /api/users` (Admin only)

Create a new user.

**Request:**

```json
{
  "username": "newuser",
  "password": "password123",
  "role": "normal"
}
```

**Response (201):**

```json
{
  "id": 3,
  "username": "newuser",
  "role": "normal",
  "created_at": "2026-08-31T13:40:00"
}
```

**Error (400):**

- Username already exists
- Password too short (< 6 characters)
- Empty username or password
- Invalid role

**Error (401/403):** Authentication/authorization failure

#### `GET /api/users/{id}` (Admin only)

Get a specific user.

**Response (200):**

```json
{
  "id": 2,
  "username": "john",
  "role": "normal",
  "created_at": "2026-08-31T13:35:00"
}
```

**Error (404):** User not found

**Error (401/403):** Authentication/authorization failure

#### `PUT /api/users/{id}/password` (Admin only)

Change a user's password.

**Request:**

```json
{
  "new_password": "newpassword123"
}
```

**Response (200):**

```json
{
  "message": "Password updated"
}
```

**Error (400):**

- Password too short (< 6 characters)
- Empty password

**Error (404):** User not found

**Error (401/403):** Authentication/authorization failure

#### `PUT /api/users/{id}/role` (Admin only)

Change a user's role.

**Request:**

```json
{
  "new_role": "admin"
}
```

**Response (200):**

```json
{
  "message": "Role updated for john"
}
```

**Error (400):**

- Attempting to remove the last administrator
- Invalid role

**Error (404):** User not found

**Error (401/403):** Authentication/authorization failure

#### `DELETE /api/users/{id}` (Admin only)

Delete a user.

**Response (200):**

```json
{
  "message": "User john deleted"
}
```

**Error (400):**

- Attempting to delete own account
- Attempting to delete the last administrator

**Error (404):** User not found

**Error (401/403):** Authentication/authorization failure

---

## Security Protections

### Last Administrator Protection

The system prevents removal of the last administrator:

1. Role change: Cannot change the last admin to `normal`
2. Deletion: Cannot delete the last remaining admin

**Error message:** "cannot remove the last administrator"

This is enforced at the API level (backend), not just UI.

### Self-Deletion Protection

Administrators cannot accidentally delete their own account:

1. Deletion attempt of current user is rejected
2. Error message: "cannot delete your own account"

This is enforced at the API level (backend), not just UI.

### Password Validation

1. Minimum length: 6 characters
2. Confirmation required on creation/change
3. Must match confirmation field
4. Validated at both frontend and backend

### Username Uniqueness

1. Database UNIQUE constraint on username column
2. API validation rejects duplicate usernames
3. Error message: "username already exists"

### Session Security

1. Session stored server-side (via Flask-Session)
2. Session cookie is HttpOnly (not accessible to JavaScript)
3. Session cookie is Secure (only sent over HTTPS in production)
4. Session includes user_id and user_role for authorization checks

### API Authorization

Every protected endpoint performs:

1. **Authentication check**: Is user logged in? (session exists)
2. **Authorization check**: Does user have required role?

If not authenticated: Return HTTP 401 Unauthorized

If not authorized: Return HTTP 403 Forbidden

---

## Usage Examples

### Create a Normal User

1. Log in as admin
2. Click "User Management" tile
3. Fill in form:
   - Username: `john`
   - Password: `password123`
   - Confirm Password: `password123`
   - Role: `Normal User`
4. Click "Create" button
5. Success message appears: "User created successfully"

### Change User Role

1. Log in as admin
2. Click "User Management" tile
3. In "Existing Users" table, find user
4. Click "Change Role" button
5. Select new role from dropdown
6. Click "Change Role" button
7. Success message appears: "Role updated for {username}"

### Delete User

1. Log in as admin
2. Click "User Management" tile
3. In "Existing Users" table, find user
4. Click "Delete" button
5. Confirmation modal appears
6. Click "Delete User" button
7. Success message appears: "User {username} deleted"

### Change Password

1. Log in as admin
2. Click "User Management" tile
3. In "Existing Users" table, find user
4. Click "Change Password" button
5. Enter new password
6. Enter confirmation
7. Click "Change Password" button
8. Success message appears: "Password updated for {username}"

---

## Testing

### Run Automated Tests

```bash
pytest test_user_management.py -v
```

### Test Coverage

The test suite covers:

- **Authentication**: Login with valid/invalid credentials
- **User Creation**: Success, duplicate username, short password, empty fields
- **Role Management**: Change role, last admin protection, multiple admins
- **User Deletion**: Success, self-deletion protection, last admin protection
- **Password Management**: Change password, validation
- **Authorization**: Normal user restrictions, API access control
- **Password Hashing**: Hashing, verification, irreversibility
- **UI Elements**: Tile visibility based on role

Run a specific test:

```bash
pytest test_user_management.py::TestAuthentication::test_login_success -v
```

---

## Important Files

| File | Purpose |
|------|---------|
| [app.py](C:/Users/ovidi/OneDrive/Desktop/personal%20project/Inventory/app.py) | Main Flask app with user management logic, authentication, and API endpoints |
| [templates/users.html](C:/Users/ovidi/OneDrive/Desktop/personal%20project/Inventory/templates/users.html) | User Management page UI with forms, tables, and modals |
| [templates/home.html](C:/Users/ovidi/OneDrive/Desktop/personal%20project/Inventory/templates/home.html) | Homepage with conditional User Management tile |
| [requirements.txt](C:/Users/ovidi/OneDrive/Desktop/personal%20project/Inventory/requirements.txt) | Python dependencies (includes bcrypt) |
| [test_user_management.py](C:/Users/ovidi/OneDrive/Desktop/personal%20project/Inventory/test_user_management.py) | Automated test suite for RBAC and user management |

---

## Database Migration Notes

This feature uses SQLite's `CREATE TABLE IF NOT EXISTS` for automatic schema creation. No manual migrations are required for fresh installations.

If upgrading from a version without user management:

1. A `users` table is created automatically on first run
2. Existing users must be created through the User Management interface
3. The default admin user is created if no users exist

---

## Deployment Considerations

### Docker

For Docker deployments:

1. The `users` table persists in PostgreSQL volume
2. The default admin is created on first startup
3. When recreating the application container (not database), all users persist
4. Database migrations are applied automatically

### Environment Variables

Available for customizing default admin:

```bash
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin
```

If not set, defaults to: `admin` / `admin`

### Production Security

For production deployments:

1. **Change default admin password immediately** after deployment
2. Use HTTPS (Flask-Session cookies should be Secure flag)
3. Set Flask `SECRET_KEY` to a strong random value
4. Set `SESSION_COOKIE_SECURE = True` in production
5. Set `SESSION_COOKIE_HTTPONLY = True`
6. Consider session timeout (not yet implemented)

---

## Known Limitations

1. **No password reset**: Admins must change forgotten passwords manually
2. **No session timeout**: Sessions persist until logout or browser close
3. **No activity logging**: User actions are not audited
4. **No password complexity requirements**: Only length validation (6+ chars)
5. **No email verification**: Email field not yet implemented
6. **No 2FA**: Two-factor authentication not yet implemented

---

## Future Enhancements

Potential improvements:

1. Password reset via email
2. Session timeout and re-authentication
3. User activity audit log
4. Stronger password requirements (complexity, history)
5. Email address field and verification
6. Two-factor authentication
7. User groups and permissions
8. Scheduled password expiration
9. Account lockout after failed login attempts
10. User profile page (change own password)

---

## Troubleshooting

### "Cannot remove the last administrator"

This error means you attempted to:
- Change the last admin's role to normal, or
- Delete the last remaining admin

**Solution**: Create another admin user first, then make the change.

### "Cannot delete your own account"

You tried to delete the currently logged-in admin.

**Solution**: Log in as a different admin user to delete your account.

### "Username already exists"

The username is already taken.

**Solution**: Choose a different username.

### "Password too short"

Password must be at least 6 characters.

**Solution**: Enter a password with 6 or more characters.

### Normal user cannot see User Management tile

This is correct behavior. Only admin users can see and access User Management.

**Solution**: Log in as an admin user to access user management.

---

## Contact & Support

For issues or questions about user management, review:

1. This documentation
2. Test cases in `test_user_management.py`
3. Code comments in `app.py`
4. Issue tracker (if applicable)
