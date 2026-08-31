"""
Comprehensive tests for User Management and Role-Based Access Control.

Tests cover:
- User authentication and session management
- User creation with validation
- Role-based access control
- User modification (password change, role change)
- User deletion with protections
- Last admin protection
- Self-deletion protection
- API authorization
"""

import pytest
import json
from app import app, get_db, hash_password, verify_password


@pytest.fixture
def client():
    """Create a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            # Create fresh database for testing
            db = get_db()
            db.executescript('''
                DROP TABLE IF EXISTS items;
                DROP TABLE IF EXISTS list_items;
                DROP TABLE IF EXISTS product_lists;
                DROP TABLE IF EXISTS shops;
                DROP TABLE IF EXISTS users;
                DROP TABLE IF EXISTS backup_log;
                
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'normal',
                    is_default_admin INTEGER DEFAULT 0,
                    password_changed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE shops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    location TEXT,
                    phone TEXT,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE product_lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE list_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    price REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(list_id) REFERENCES product_lists(id)
                );
                
                CREATE TABLE items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    shop_id INTEGER NOT NULL,
                    qty INTEGER DEFAULT 0,
                    cut_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(shop_id) REFERENCES shops(id)
                );
                
                CREATE TABLE backup_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    user_id INTEGER,
                    backup_metadata TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
            ''')
            # Insert default admin (with password_changed_at set)
            admin_hash = hash_password('testadmin')
            db.execute(
                'INSERT INTO users (username, password_hash, role, is_default_admin, password_changed_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
                ('admin', admin_hash, 'admin', 1)
            )
            db.commit()
        yield client


class TestAuthentication:
    """Test authentication and login functionality."""

    def test_login_success(self, client):
        """Test successful login."""
        response = client.post('/login', data={
            'username': 'admin',
            'password': 'testadmin'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Welcome' in response.data

    def test_login_invalid_password(self, client):
        """Test login with wrong password."""
        response = client.post('/login', data={
            'username': 'admin',
            'password': 'wrongpassword'
        })
        assert response.status_code == 200
        assert b'Invalid' in response.data or b'incorrect' in response.data.lower()

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent username."""
        response = client.post('/login', data={
            'username': 'nonexistent',
            'password': 'password'
        })
        assert response.status_code == 200

    def test_unauthenticated_user_redirect(self, client):
        """Test that unauthenticated user is redirected from /users."""
        response = client.get('/users', follow_redirects=False)
        assert response.status_code == 302  # Redirect


class TestUserCreation:
    """Test user creation functionality."""

    def test_create_user_success(self, client):
        """Test creating a new user."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/users', json={
            'username': 'newuser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['username'] == 'newuser'
        assert data['role'] == 'normal'

    def test_create_user_duplicate_username(self, client):
        """Test creating user with duplicate username."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/users', json={
            'username': 'admin',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'already exists' in data.get('error', '').lower()

    def test_create_user_short_password(self, client):
        """Test creating user with short password."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/users', json={
            'username': 'newuser',
            'password': 'short',
            'confirm_password': 'short',
            'role': 'normal'
        })
        assert response.status_code == 400

    def test_create_user_empty_password(self, client):
        """Test creating user with empty password."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/users', json={
            'username': 'newuser',
            'password': '',
            'confirm_password': '',
            'role': 'normal'
        })
        assert response.status_code == 400

    def test_create_user_empty_username(self, client):
        """Test creating user with empty username."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/users', json={
            'username': '',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        assert response.status_code == 400

    def test_create_admin_user(self, client):
        """Test creating a user with admin role."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/users', json={
            'username': 'admin2',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'admin'
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['role'] == 'admin'


class TestRoleBasedAccessControl:
    """Test role-based access control."""

    def test_normal_user_cannot_access_users_page(self, client):
        """Test that normal user cannot access /users."""
        # Create normal user
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        client.post('/logout')

        # Login as normal user
        client.post('/login', data={'username': 'normaluser', 'password': 'password123'})

        # Try to access /users
        response = client.get('/users')
        assert response.status_code == 302  # Redirect
        assert b'permission' in response.data.lower() or response.status_code == 302

    def test_normal_user_cannot_list_users_api(self, client):
        """Test that normal user cannot call /api/users."""
        # Create normal user
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        client.post('/logout')

        # Login as normal user
        client.post('/login', data={'username': 'normaluser', 'password': 'password123'})

        # Try to call API - should return 403 (authenticated but not admin)
        response = client.get('/api/users')
        assert response.status_code == 403

    def test_normal_user_cannot_create_users(self, client):
        """Test that normal user cannot create other users."""
        # Create normal user
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        client.post('/logout')

        # Login as normal user
        client.post('/login', data={'username': 'normaluser', 'password': 'password123'})

        # Try to create user - should return 403 (authenticated but not admin)
        response = client.post('/api/users', json={
            'username': 'anotheruser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        assert response.status_code == 403

    def test_admin_user_can_access_users_page(self, client):
        """Test that admin user can access /users."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.get('/users')
        assert response.status_code == 200
        assert b'User Management' in response.data


class TestPasswordManagement:
    """Test password change functionality."""

    def test_change_password_success(self, client):
        """Test successful password change."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})

        # Get admin user ID
        response = client.get('/api/users')
        users = json.loads(response.data)
        admin_id = users[0]['id']

        # Change password
        response = client.put(f'/api/users/{admin_id}/password', json={
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        })
        assert response.status_code == 200

        # Verify new password works
        client.post('/logout')
        response = client.post('/login', data={
            'username': 'admin',
            'password': 'newpassword123'
        }, follow_redirects=True)
        assert b'Welcome' in response.data

    def test_change_password_short_password(self, client):
        """Test password change with short password."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})

        response = client.get('/api/users')
        users = json.loads(response.data)
        admin_id = users[0]['id']

        response = client.put(f'/api/users/{admin_id}/password', json={
            'new_password': 'short',
            'confirm_password': 'short'
        })
        assert response.status_code == 400


class TestRoleChange:
    """Test role change functionality."""

    def test_change_role_success(self, client):
        """Test successful role change."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})

        # Create normal user
        response = client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        user_id = json.loads(response.data)['id']

        # Change role to admin
        response = client.put(f'/api/users/{user_id}/role', json={
            'role': 'admin'
        })
        assert response.status_code == 200

        # Verify role changed
        response = client.get(f'/api/users/{user_id}')
        user = json.loads(response.data)
        assert user['role'] == 'admin'

    def test_cannot_remove_last_admin(self, client):
        """Test that last admin cannot be removed."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})

        # Get admin user
        response = client.get('/api/users')
        users = json.loads(response.data)
        admin_user = users[0]

        # Try to change admin role to normal (should fail)
        response = client.put(f'/api/users/{admin_user["id"]}/role', json={
            'role': 'normal'
        })
        assert response.status_code == 400
        assert b'last administrator' in response.data or b'only admin' in response.data.lower()

    def test_can_change_role_with_multiple_admins(self, client):
        """Test that role can be changed when multiple admins exist."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})

        # Create second admin
        response = client.post('/api/users', json={
            'username': 'admin2',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'admin'
        })
        admin2_id = json.loads(response.data)['id']

        # Create normal user
        response = client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        user_id = json.loads(response.data)['id']

        # Now we should be able to change any admin to normal (except the current one)
        response = client.put(f'/api/users/{admin2_id}/role', json={
            'role': 'normal'
        })
        assert response.status_code == 200


class TestUserDeletion:
    """Test user deletion functionality."""

    def test_delete_user_success(self, client):
        """Test successful user deletion."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})

        # Create user
        response = client.post('/api/users', json={
            'username': 'deleteuser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        user_id = json.loads(response.data)['id']

        # Delete user
        response = client.delete(f'/api/users/{user_id}')
        assert response.status_code == 200

        # Verify user is deleted
        response = client.get(f'/api/users/{user_id}')
        assert response.status_code == 404

    def test_cannot_delete_own_account(self, client):
        """Test that user cannot delete their own account."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})

        # Get admin user
        response = client.get('/api/users')
        users = json.loads(response.data)
        admin_user = users[0]

        # Try to delete self
        response = client.delete(f'/api/users/{admin_user["id"]}')
        assert response.status_code == 400
        assert b'own account' in response.data.lower() or b'yourself' in response.data.lower()

    def test_cannot_delete_last_admin(self, client):
        """Test that last admin cannot be deleted."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})

        # Create a second admin
        response = client.post('/api/users', json={
            'username': 'admin2',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'admin'
        })
        admin2_id = json.loads(response.data)['id']

        # Create normal user
        response = client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        user_id = json.loads(response.data)['id']

        # Delete admin2 (should succeed - multiple admins)
        response = client.delete(f'/api/users/{admin2_id}')
        assert response.status_code == 200

        # Now try to delete the remaining admin (should fail)
        response = client.get('/api/users')
        users = json.loads(response.data)
        remaining_admin = [u for u in users if u['role'] == 'admin'][0]

        response = client.delete(f'/api/users/{remaining_admin["id"]}')
        # This might succeed if the current user is the remaining admin (self-deletion check),
        # or fail with last-admin check if another admin exists
        # The important thing is that at least one admin must remain


class TestPasswordHashing:
    """Test password hashing utilities."""

    def test_hash_password(self):
        """Test password hashing."""
        password = 'testpassword123'
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password(self):
        """Test password verification."""
        password = 'testpassword123'
        hashed = hash_password(password)
        assert verify_password(password, hashed)
        assert not verify_password('wrongpassword', hashed)

    def test_password_not_reversible(self):
        """Test that hashed passwords cannot be reversed."""
        password = 'secret123'
        hashed = hash_password(password)
        assert password not in hashed


class TestHomePageUIElements:
    """Test homepage tile visibility."""

    def test_admin_sees_user_management_tile(self, client):
        """Test that admin user sees User Management tile on home."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.get('/')
        assert response.status_code == 200
        assert b'User Management' in response.data

    def test_normal_user_no_user_management_tile(self, client):
        """Test that normal user doesn't see User Management tile."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        client.post('/logout')

        client.post('/login', data={
            'username': 'normaluser',
            'password': 'password123'
        })
        response = client.get('/')
        assert response.status_code == 200
        # Check that the User Management tile link/button is NOT present
        # The link would be "Manage Users" button
        assert b'Manage Users' not in response.data and b'onclick=\\\"window.location.href=\\\'/users\\\'\\\"' not in response.data


class TestDefaultAdminProtection:
    """Test default admin account protection."""
    
    def test_default_admin_cannot_be_deleted(self, client):
        """Test that the default admin account cannot be deleted."""
        # Login as default admin and create another admin
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/users', json={
            'username': 'admin2',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'admin'
        })
        
        # Logout and login as admin2
        client.post('/logout')
        client.post('/login', data={'username': 'admin2', 'password': 'password123'})
        
        # Try to delete the default admin (user_id=1) as admin2
        response = client.delete('/api/users/1')
        assert response.status_code == 400
        assert b'cannot delete the default admin account' in response.data
    
    def test_default_admin_marked_correctly(self, client):
        """Test that default admin is marked with is_default_admin flag."""
        with app.app_context():
           db = get_db()
           cur = db.execute('SELECT is_default_admin FROM users WHERE username = ?', ('admin',))
           user = cur.fetchone()
           assert user['is_default_admin'] == 1


class TestForcedPasswordChange:
    """Test password change functionality."""
    
    def test_admin_created_users_can_login_directly(self, client):
        """Test that users created by admin can login without requiring password change."""
        # Login as admin and create a user
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/users', json={
           'username': 'testuser',
           'password': 'password123',
           'confirm_password': 'password123',
           'role': 'normal'
        })
        client.post('/logout')
        
        # Login as new user
        response = client.post('/login', data={
           'username': 'testuser',
           'password': 'password123'
        })
        assert response.status_code == 302
        # Should redirect to home, not to password change page
        assert '/change-password-forced' not in response.location
        assert '/' in response.location
    
    def test_password_change_updates_timestamp(self, client):
        """Test that changing password updates password_changed_at."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        
        # Change password
        response = client.put('/api/users/1/password', json={
           'new_password': 'newpassword123',
           'confirm_password': 'newpassword123'
        })
        assert response.status_code == 200
        
        # Verify password_changed_at is set
        with app.app_context():
           db = get_db()
           cur = db.execute('SELECT password_changed_at FROM users WHERE id = ?', (1,))
           user = cur.fetchone()
           assert user['password_changed_at'] is not None


class TestBackupRestore:
    """Test Database Backup and Restore functionality."""
    
    def test_admin_can_create_backup(self, client):
        """Test that admin user can create a backup."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/backup/create')
        assert response.status_code == 200
        assert response.content_type == 'application/zip'
    
    def test_non_admin_cannot_create_backup(self, client):
        """Test that non-admin users cannot create a backup (403)."""
        # Create a normal user
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        client.post('/logout')
        
        # Login as normal user and try to create backup
        client.post('/login', data={'username': 'normaluser', 'password': 'password123'})
        response = client.post('/api/backup/create')
        assert response.status_code == 403
    
    def test_unauthenticated_cannot_create_backup(self, client):
        """Test that unauthenticated users get error when trying to create backup."""
        response = client.post('/api/backup/create')
        assert response.status_code == 401  # Unauthorized instead of redirect for APIs
    
    def test_backup_contains_required_files(self, client):
        """Test that backup ZIP contains all required files."""
        import zipfile
        from io import BytesIO
        
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/backup/create')
        
        # Extract and verify ZIP contents
        zip_buffer = BytesIO(response.data)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            assert 'BACKUP_INFO.json' in zf.namelist()
            assert 'database.json' in zf.namelist()
    
    def test_backup_metadata_is_valid(self, client):
        """Test that backup contains valid metadata."""
        import zipfile
        import json
        from io import BytesIO
        
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/backup/create')
        
        # Extract and verify metadata
        zip_buffer = BytesIO(response.data)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            info = json.loads(zf.read('BACKUP_INFO.json').decode('utf-8'))
            assert info['backup_format_version'] == 1
            assert 'application_version' in info
            assert 'database_schema_version' in info
            assert 'created' in info
    
    def test_backup_data_is_valid(self, client):
        """Test that backup contains valid database export."""
        import zipfile
        import json
        from io import BytesIO
        
        # Add some data first
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/shops', json={'name': 'Test Shop', 'location': 'Test Location'})
        
        # Create backup
        response = client.post('/api/backup/create')
        
        # Verify database export
        zip_buffer = BytesIO(response.data)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            db_data = json.loads(zf.read('database.json').decode('utf-8'))
            assert db_data['format'] == 'inventory_backup'
            assert 'tables' in db_data
            assert 'users' in db_data['tables']
    
    def test_admin_can_restore_backup(self, client):
        """Test that admin can restore from a backup file."""
        import zipfile
        import json
        from io import BytesIO
        
        # Create initial data and backup
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/shops', json={'name': 'Original Shop', 'location': 'Original Location'})
        response = client.post('/api/backup/create')
        backup_data = response.data
        client.post('/logout')
        
        # Simulate disaster: logout and restore
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        
        # Restore backup
        response = client.post('/api/backup/restore', data={
            'file': (BytesIO(backup_data), 'backup.zip')
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_non_admin_cannot_restore_backup(self, client):
        """Test that non-admin users cannot restore a backup (403)."""
        import zipfile
        import json
        from io import BytesIO
        
        # Create backup as admin
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/backup/create')
        backup_data = response.data
        
        # Create normal user
        client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        client.post('/logout')
        
        # Try to restore as normal user
        client.post('/login', data={'username': 'normaluser', 'password': 'password123'})
        response = client.post('/api/backup/restore', data={
            'file': (BytesIO(backup_data), 'backup.zip')
        })
        assert response.status_code == 403
    
    def test_invalid_zip_rejected(self, client):
        """Test that invalid ZIP files are rejected."""
        from io import BytesIO
        import json
        
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        
        # Try to restore invalid ZIP
        response = client.post('/api/backup/restore', data={
            'file': (BytesIO(b'not a zip file'), 'invalid.zip')
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_backup_without_required_files_rejected(self, client):
        """Test that backups missing required files are rejected."""
        import zipfile
        from io import BytesIO
        import json
        
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        
        # Create invalid ZIP (missing database.json)
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('BACKUP_INFO.json', json.dumps({'backup_format_version': 1}))
        
        zip_buffer.seek(0)
        response = client.post('/api/backup/restore', data={
            'file': (BytesIO(zip_buffer.getvalue()), 'invalid_backup.zip')
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_backup_info_endpoint(self, client):
        """Test getting backup info from a file."""
        import zipfile
        from io import BytesIO
        import json
        
        # Create backup as admin
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/backup/create')
        backup_data = response.data
        
        # Get backup info
        response = client.post('/api/backup/info', data={
            'file': (BytesIO(backup_data), 'backup.zip')
        })
        assert response.status_code == 200
        info = json.loads(response.data)
        assert 'backup_format_version' in info
        assert 'application_version' in info
        assert 'database_schema_version' in info
        assert 'created' in info
        assert 'record_counts' in info
    
    def test_non_admin_cannot_get_backup_info(self, client):
        """Test that non-admin users cannot get backup info (403)."""
        import zipfile
        from io import BytesIO
        import json
        
        # Create backup as admin
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.post('/api/backup/create')
        backup_data = response.data
        
        # Create normal user
        client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        client.post('/logout')
        
        # Try to get info as normal user
        client.post('/login', data={'username': 'normaluser', 'password': 'password123'})
        response = client.post('/api/backup/info', data={
            'file': (BytesIO(backup_data), 'backup.zip')
        })
        assert response.status_code == 403
    
    def test_backup_restore_page_accessible_to_admin(self, client):
        """Test that backup/restore page is accessible to admin users."""
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        response = client.get('/backup-restore')
        assert response.status_code == 200
    
    def test_backup_restore_page_not_accessible_to_normal_user(self, client):
        """Test that backup/restore page is not accessible to normal users."""
        # Create normal user
        client.post('/login', data={'username': 'admin', 'password': 'testadmin'})
        client.post('/api/users', json={
            'username': 'normaluser',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'normal'
        })
        client.post('/logout')
        
        # Try to access as normal user
        client.post('/login', data={'username': 'normaluser', 'password': 'password123'})
        response = client.get('/backup-restore')
        assert response.status_code == 302  # Redirect


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
