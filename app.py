from flask import Flask, g, jsonify, request, render_template, redirect, url_for, session, flash, send_file
import sqlite3
import os
import sys
import bcrypt
from functools import wraps
from datetime import datetime, timedelta
import json
import zipfile
import tempfile
import shutil
from io import BytesIO

# Determine if using PostgreSQL (Docker) or SQLite (local development)
USE_POSTGRES = os.environ.get('DB_HOST') is not None

if USE_POSTGRES:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
        sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.path.join(DB_DIR, 'inventory.db')

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret-change-in-production')
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Environment configuration
FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
if FLASK_ENV == 'production':
    FLASK_DEBUG = False  # Never debug in production

# Simple credential from env (for demo). Set INVENTORY_USER and INVENTORY_PASS in environment for production.
ADMIN_USER = os.environ.get('INVENTORY_USER', 'admin')
ADMIN_PASS = os.environ.get('INVENTORY_PASS', 'admin')
WEIGHT_SCHEMA_READY = False


# ============= PASSWORD HASHING UTILITIES =============
def hash_password(password):
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password, password_hash):
    """Verify a password against a hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


# ============= DATABASE WRAPPER FOR PSYCOPG2 =============
class PostgreSQLCursorWrapper:
    """Wrapper for psycopg2 cursor to provide SQLite-like interface."""
    
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None
    
    def fetchone(self):
        return self.cursor.fetchone()
    
    def fetchall(self):
        return self.cursor.fetchall()
    
    def __getattr__(self, name):
        # Delegate other attributes to the underlying cursor
        return getattr(self.cursor, name)


class PostgreSQLWrapper:
    """Wrapper to provide SQLite-like interface for psycopg2 connections."""
    
    def __init__(self, conn):
        self.conn = conn
    
    def _convert_placeholders(self, query):
        """Convert SQLite '?' placeholders to PostgreSQL '%s' placeholders."""
        # Replace ? with %s for PostgreSQL compatibility
        return query.replace('?', '%s')
    
    def execute(self, query, params=None):
        """Execute a query and return a cursor-like object."""
        cur = self.conn.cursor()
        query = self._convert_placeholders(query)
        
        # For INSERT statements, use RETURNING id to get the last inserted ID
        is_insert = query.strip().upper().startswith('INSERT')
        if is_insert and 'RETURNING' not in query.upper():
            query = query.rstrip(';').rstrip() + ' RETURNING id'
        
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        # For INSERT statements, fetch the returned ID
        wrapper = PostgreSQLCursorWrapper(cur)
        if is_insert:
            result = cur.fetchone()
            if result:
                # Handle both dict results (RealDictCursor) and tuple results
                if isinstance(result, dict):
                    wrapper.lastrowid = result.get('id')
                else:
                    # Tuple result from regular cursor
                    wrapper.lastrowid = result[0]
        
        return wrapper
    
    def executescript(self, script):
        """Execute multiple SQL statements."""
        cur = self.conn.cursor()
        cur.execute(script)
        self.conn.commit()
        return PostgreSQLCursorWrapper(cur)
    
    def commit(self):
        """Commit the transaction."""
        self.conn.commit()
    
    def rollback(self):
        """Rollback the transaction."""
        self.conn.rollback()
    
    def close(self):
        """Close the connection."""
        self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def get_db():
    if 'db' not in g:
        if USE_POSTGRES:
            # Connect to PostgreSQL
            try:
                conn = psycopg2.connect(
                    host=os.environ.get('DB_HOST'),
                    port=os.environ.get('DB_PORT', '5432'),
                    database=os.environ.get('DB_NAME', 'inventory'),
                    user=os.environ.get('DB_USER', 'inventory_app'),
                    password=os.environ.get('DB_PASSWORD', ''),
                    cursor_factory=RealDictCursor
                )
                g.db = PostgreSQLWrapper(conn)
                
                # Initialize/sync admin user credentials
                try:
                    # Ensure the configured INVENTORY_USER/INVENTORY_PASS exists and is admin
                    hashed_password = hash_password(ADMIN_PASS)
                    
                    # Check if the configured admin user exists
                    cur = g.db.execute('SELECT id FROM users WHERE username = %s', (ADMIN_USER,))
                    existing_admin = cur.fetchone()
                    
                    if existing_admin:
                        # User exists - update password and ensure admin role
                        g.db.execute(
                            'UPDATE users SET password_hash = %s, role = %s, is_default_admin = 1, password_changed_at = CURRENT_TIMESTAMP WHERE username = %s',
                            (hashed_password, 'admin', ADMIN_USER)
                        )
                        g.db.commit()
                        print(f"[AUTH] Updated admin credentials for: {ADMIN_USER}")
                    else:
                        # User does NOT exist - create it
                        g.db.execute(
                            'INSERT INTO users (username, password_hash, role, is_default_admin, password_changed_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)',
                            (ADMIN_USER, hashed_password, 'admin', 1)
                        )
                        g.db.commit()
                        print(f"[AUTH] Created admin user: {ADMIN_USER}")
                except Exception as e:
                    print(f"[AUTH] Warning: Could not initialize/sync admin user: {e}")
            except psycopg2.Error as e:
                print(f"PostgreSQL connection error: {e}")
                raise
        else:
            # Connect to SQLite (local development)
            os.makedirs(DB_DIR, exist_ok=True)
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            g.db = conn
            
            # Initialize SQLite tables
            with conn:
                # Users table with role-based access control
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'normal',
                        is_default_admin INTEGER DEFAULT 0,
                        password_changed_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.execute(
                    'CREATE TABLE IF NOT EXISTS shops (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, location TEXT, phone TEXT, email TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'
                )
                conn.execute(
                    'CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, shop_id INTEGER NOT NULL, qty INTEGER NOT NULL, cut_type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(shop_id) REFERENCES shops(id) ON DELETE CASCADE)'
                )
                conn.execute(
                    'CREATE TABLE IF NOT EXISTS product_lists (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'
                )
                conn.execute(
                    'CREATE TABLE IF NOT EXISTS list_items (id INTEGER PRIMARY KEY AUTOINCREMENT, list_id INTEGER NOT NULL, item_name TEXT NOT NULL, qty INTEGER NOT NULL, cut_type TEXT, price REAL, FOREIGN KEY(list_id) REFERENCES product_lists(id) ON DELETE CASCADE)'
                )
                conn.execute(
                    'CREATE TABLE IF NOT EXISTS backup_log (id INTEGER PRIMARY KEY AUTOINCREMENT, operation TEXT NOT NULL, status TEXT NOT NULL, user_id INTEGER, backup_metadata TEXT, error_message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id))'
                )
                
                # Database migrations - add new columns if they don't exist
                # Add is_default_admin column
                try:
                    conn.execute('ALTER TABLE users ADD COLUMN is_default_admin INTEGER DEFAULT 0')
                except:
                    pass  # Column already exists
                
                # Add password_changed_at column
                try:
                    conn.execute('ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP')
                except:
                    pass  # Column already exists
                
                # Add created_at and updated_at to items table
                try:
                    conn.execute('ALTER TABLE items ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                except:
                    pass  # Column already exists
                
                try:
                    conn.execute('ALTER TABLE items ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                except:
                    pass  # Column already exists
                
                # Add created_at and updated_at to list_items table
                try:
                    conn.execute('ALTER TABLE list_items ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                except:
                    pass  # Column already exists
                
                try:
                    conn.execute('ALTER TABLE list_items ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                except:
                    pass  # Column already exists
                
                # Initialize default admin user if no users exist
                cur = conn.execute('SELECT COUNT(*) as count FROM users')
                if cur.fetchone()['count'] == 0:
                    hashed_password = hash_password(ADMIN_PASS)
                    conn.execute(
                        'INSERT INTO users (username, password_hash, role, is_default_admin, password_changed_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
                        (ADMIN_USER, hashed_password, 'admin', 1)
                    )
                    print(f"Initialized default admin user: {ADMIN_USER}")
                else:
                    # Mark the original admin user as default admin if not already marked
                    conn.execute('UPDATE users SET is_default_admin = 1 WHERE username = ? AND is_default_admin = 0', (ADMIN_USER,))
                    # Set password_changed_at for default admin if it's NULL (for existing databases)
                    conn.execute('UPDATE users SET password_changed_at = CURRENT_TIMESTAMP WHERE username = ? AND password_changed_at IS NULL', (ADMIN_USER,))
    
    ensure_weight_inventory_schema(g.db)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def ensure_weight_inventory_schema(db):
    """Apply idempotent, in-app migrations for Docker volumes created by older releases."""
    global WEIGHT_SCHEMA_READY
    if WEIGHT_SCHEMA_READY:
        return
    if USE_POSTGRES:
        statements = [
            'ALTER TABLE items ALTER COLUMN qty TYPE NUMERIC(12,3)',
            'ALTER TABLE items ADD COLUMN IF NOT EXISTS sku TEXT',
            'ALTER TABLE items ADD COLUMN IF NOT EXISTS selling_price NUMERIC(12,2) DEFAULT 0',
            'ALTER TABLE items ADD COLUMN IF NOT EXISTS cost_price NUMERIC(12,2) DEFAULT 0',
            'ALTER TABLE items ADD COLUMN IF NOT EXISTS low_stock_threshold NUMERIC(12,3) DEFAULT 0',
            '''CREATE TABLE IF NOT EXISTS stock_receipts (id SERIAL PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE, quantity_kg NUMERIC(12,3) NOT NULL, cost_price NUMERIC(12,2) NOT NULL DEFAULT 0, selling_price NUMERIC(12,2) NOT NULL DEFAULT 0, batch_number TEXT, expiration_date DATE, user_id INTEGER REFERENCES users(id), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
            '''CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT, quantity_kg NUMERIC(12,3) NOT NULL, price_per_kg NUMERIC(12,2) NOT NULL, total_amount NUMERIC(12,2) NOT NULL, customer_name TEXT, user_id INTEGER REFERENCES users(id), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
            '''CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, item_id INTEGER REFERENCES items(id) ON DELETE CASCADE, kind TEXT NOT NULL, message TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
        ]
    else:
        statements = [
            'ALTER TABLE items ADD COLUMN sku TEXT',
            'ALTER TABLE items ADD COLUMN selling_price REAL DEFAULT 0',
            'ALTER TABLE items ADD COLUMN cost_price REAL DEFAULT 0',
            'ALTER TABLE items ADD COLUMN low_stock_threshold REAL DEFAULT 0',
            '''CREATE TABLE IF NOT EXISTS stock_receipts (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE, quantity_kg REAL NOT NULL, cost_price REAL NOT NULL DEFAULT 0, selling_price REAL NOT NULL DEFAULT 0, batch_number TEXT, expiration_date TEXT, user_id INTEGER REFERENCES users(id), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
            '''CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT, quantity_kg REAL NOT NULL, price_per_kg REAL NOT NULL, total_amount REAL NOT NULL, customer_name TEXT, user_id INTEGER REFERENCES users(id), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
            '''CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER REFERENCES items(id) ON DELETE CASCADE, kind TEXT NOT NULL, message TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
        ]
    for statement in statements:
        try:
            db.execute(statement)
            db.commit()
        except Exception as error:
            # Duplicate SQLite columns are expected after the first run.
            db.rollback()
            if 'duplicate column' not in str(error).lower():
                raise
    WEIGHT_SCHEMA_READY = True


def central_shop_id(db):
    """Keep one logical location without deleting legacy shop records."""
    shop = db.execute('SELECT id FROM shops WHERE name = ?', ('Central Stock',)).fetchone()
    if shop:
        return shop['id']
    result = db.execute('INSERT INTO shops (name, location) VALUES (?, ?)', ('Central Stock', 'Central location'))
    db.commit()
    return result.lastrowid


def number(value, field, minimum=0):
    try:
        parsed = round(float(value), 3)
    except (ValueError, TypeError):
        raise ValueError(f'{field} must be a number')
    if parsed < minimum:
        raise ValueError(f'{field} must be at least {minimum}')
    return parsed


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        # Check if user is forced to change password
        if session.get('force_password_change'):
            return redirect(url_for('change_password_forced'))
        return fn(*args, **kwargs)
    return wrapper


def api_login_required(fn):
    """Decorator to require login for API endpoints. Returns 401 instead of redirecting."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'error': 'unauthorized'}), 401
        # Check if user is forced to change password
        if session.get('force_password_change'):
            return jsonify({'error': 'password change required'}), 403
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """Decorator to require admin role for API endpoints."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'error': 'unauthorized'}), 401
        
        db = get_db()
        cur = db.execute('SELECT role FROM users WHERE username = ?', (session['user'],))
        user = cur.fetchone()
        
        if not user or user['role'] != 'admin':
            return jsonify({'error': 'forbidden'}), 403
        
        return fn(*args, **kwargs)
    return wrapper


@app.route('/')
@login_required
def home():
    return redirect(url_for('stock'))


@app.route('/inventory')
@login_required
def inventory():
    return render_template('index.html', user=session.get('user'))


@app.route('/stock')
@login_required
def stock():
    """Mobile-first single-location stock and sales screen."""
    return render_template('stock.html', user=session.get('user'))


@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html', user=session.get('user'))


def refresh_notifications(db):
    """Generate de-duplicated low-stock and expiry alerts for the bell."""
    central_id = central_shop_id(db)
    items = db.execute('SELECT id, name, qty, low_stock_threshold FROM items WHERE shop_id = ?', (central_id,)).fetchall()
    for item in items:
        if float(item['low_stock_threshold'] or 0) > 0 and float(item['qty']) <= float(item['low_stock_threshold']):
            message = f"{item['name']} is low: {float(item['qty']):.3f} kg remaining."
            existing = db.execute('SELECT id FROM notifications WHERE item_id = ? AND kind = ? AND message = ?', (item['id'], 'low_stock', message)).fetchone()
            if not existing:
                db.execute('INSERT INTO notifications (item_id, kind, message) VALUES (?, ?, ?)', (item['id'], 'low_stock', message))
    cutoff = (datetime.now() + timedelta(days=7)).date().isoformat()
    receipts = db.execute('''SELECT r.id, r.item_id, r.batch_number, r.expiration_date, i.name
                             FROM stock_receipts r JOIN items i ON i.id = r.item_id
                             WHERE r.expiration_date IS NOT NULL AND r.expiration_date <= ?''', (cutoff,)).fetchall()
    for receipt in receipts:
        message = f"{receipt['name']} batch {receipt['batch_number'] or '—'} expires on {receipt['expiration_date']}."
        existing = db.execute('SELECT id FROM notifications WHERE item_id = ? AND kind = ? AND message = ?', (receipt['item_id'], 'expiry', message)).fetchone()
        if not existing:
            db.execute('INSERT INTO notifications (item_id, kind, message) VALUES (?, ?, ?)', (receipt['item_id'], 'expiry', message))
    db.commit()


@app.route('/api/central/items', methods=['GET', 'POST'])
@api_login_required
def central_items():
    db = get_db()
    central_id = central_shop_id(db)
    if request.method == 'GET':
        rows = db.execute('''SELECT id, name, sku, qty, selling_price, cost_price, low_stock_threshold,
                             ROUND(qty * selling_price, 2) AS stock_value
                             FROM items WHERE shop_id = ? ORDER BY name''', (central_id,)).fetchall()
        return jsonify([dict(row) for row in rows])
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Product name is required'}), 400
    try:
        qty = number(data.get('quantity_kg', 0), 'Quantity')
        selling = number(data.get('selling_price', 0), 'Selling price')
        cost = number(data.get('cost_price', 0), 'Cost price')
        threshold = number(data.get('low_stock_threshold', 0), 'Low-stock threshold')
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    existing = db.execute('SELECT id FROM items WHERE shop_id = ? AND lower(name) = lower(?)', (central_id, name)).fetchone()
    if existing:
        return jsonify({'error': 'A product with this name already exists'}), 409
    result = db.execute('''INSERT INTO items (name, shop_id, qty, sku, selling_price, cost_price, low_stock_threshold)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''', (name, central_id, qty, data.get('sku', '').strip() or None, selling, cost, threshold))
    if qty > 0:
        db.execute('''INSERT INTO stock_receipts (item_id, quantity_kg, cost_price, selling_price, batch_number, expiration_date, user_id)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''', (result.lastrowid, qty, cost, selling, data.get('batch_number', '').strip() or None, data.get('expiration_date') or None, session.get('user_id')))
    db.commit()
    return jsonify({'id': result.lastrowid}), 201


@app.route('/api/central/items/<int:item_id>/receive', methods=['POST'])
@api_login_required
def receive_stock(item_id):
    data = request.get_json() or {}
    try:
        qty = number(data.get('quantity_kg'), 'Quantity', 0.001)
        cost = number(data.get('cost_price', 0), 'Cost price')
        selling = number(data.get('selling_price', 0), 'Selling price')
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    db = get_db()
    item = db.execute('SELECT id FROM items WHERE id = ? AND shop_id = ?', (item_id, central_shop_id(db))).fetchone()
    if not item:
        return jsonify({'error': 'Product not found'}), 404
    db.execute('UPDATE items SET qty = qty + ?, cost_price = ?, selling_price = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (qty, cost, selling, item_id))
    db.execute('''INSERT INTO stock_receipts (item_id, quantity_kg, cost_price, selling_price, batch_number, expiration_date, user_id)
                  VALUES (?, ?, ?, ?, ?, ?, ?)''', (item_id, qty, cost, selling, data.get('batch_number', '').strip() or None, data.get('expiration_date') or None, session.get('user_id')))
    db.commit()
    return jsonify({'success': True})


@app.route('/api/central/items/<int:item_id>/sell', methods=['POST'])
@api_login_required
def sell_stock(item_id):
    data = request.get_json() or {}
    try:
        qty = number(data.get('quantity_kg'), 'Quantity', 0.001)
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    db = get_db()
    item = db.execute('SELECT id, name, qty, selling_price FROM items WHERE id = ? AND shop_id = ?', (item_id, central_shop_id(db))).fetchone()
    if not item:
        return jsonify({'error': 'Product not found'}), 404
    if float(item['qty']) < qty:
        return jsonify({'error': f"Only {float(item['qty']):.3f} kg is available"}), 400
    # A sale may override the price, but an omitted/blank value always uses the
    # product's current stock selling price per kilogram.
    requested_price = data.get('price_per_kg')
    price = number(item['selling_price'] if requested_price in (None, '') else requested_price, 'Price per kg')
    total = round(qty * price, 2)
    db.execute('UPDATE items SET qty = qty - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (qty, item_id))
    db.execute('''INSERT INTO sales (item_id, quantity_kg, price_per_kg, total_amount, customer_name, user_id)
                  VALUES (?, ?, ?, ?, ?, ?)''', (item_id, qty, price, total, data.get('customer_name', '').strip() or None, session.get('user_id')))
    db.commit()
    refresh_notifications(db)
    return jsonify({'success': True, 'total_amount': total})


@app.route('/api/dashboard', methods=['GET'])
@api_login_required
def dashboard():
    db = get_db()
    central_id = central_shop_id(db)
    refresh_notifications(db)
    stock = db.execute('SELECT COALESCE(SUM(qty * selling_price), 0) AS value, COALESCE(SUM(qty), 0) AS kg FROM items WHERE shop_id = ?', (central_id,)).fetchone()
    today = db.execute("SELECT COALESCE(SUM(quantity_kg), 0) AS kg, COALESCE(SUM(total_amount), 0) AS revenue FROM sales WHERE DATE(created_at) = DATE(CURRENT_TIMESTAMP)").fetchone()
    return jsonify({'stock_value': float(stock['value']), 'stock_kg': float(stock['kg']), 'today_kg': float(today['kg']), 'today_revenue': float(today['revenue'])})


@app.route('/api/reports/movement', methods=['GET'])
@api_login_required
def movement_report():
    """Value and kilogram movement report; deliberately excludes payment/invoice data."""
    db = get_db()
    start = request.args.get('start') or datetime.now().replace(day=1).date().isoformat()
    end = request.args.get('end') or datetime.now().date().isoformat()
    incoming = db.execute('''SELECT COALESCE(SUM(quantity_kg), 0) AS kg,
                             COALESCE(SUM(quantity_kg * cost_price), 0) AS amount
                             FROM stock_receipts WHERE DATE(created_at) BETWEEN DATE(?) AND DATE(?)''', (start, end)).fetchone()
    outgoing = db.execute('''SELECT COALESCE(SUM(quantity_kg), 0) AS kg,
                             COALESCE(SUM(total_amount), 0) AS amount
                             FROM sales WHERE DATE(created_at) BETWEEN DATE(?) AND DATE(?)''', (start, end)).fetchone()
    return jsonify({'start': start, 'end': end,
                    'incoming_kg': float(incoming['kg']), 'incoming_amount': float(incoming['amount']),
                    'outgoing_kg': float(outgoing['kg']), 'outgoing_amount': float(outgoing['amount'])})


@app.route('/api/reports/activity', methods=['GET'])
@api_login_required
def activity_report():
    """Detailed, date-filtered sales and stock-change history with responsible user."""
    db = get_db()
    start = request.args.get('start') or datetime.now().replace(day=1).date().isoformat()
    end = request.args.get('end') or datetime.now().date().isoformat()
    sales = db.execute('''SELECT s.id, s.created_at, i.name AS product_name, s.quantity_kg,
                          s.price_per_kg, s.total_amount, s.customer_name,
                          COALESCE(u.username, 'Deleted user') AS username
                          FROM sales s JOIN items i ON i.id = s.item_id
                          LEFT JOIN users u ON u.id = s.user_id
                          WHERE DATE(s.created_at) BETWEEN DATE(?) AND DATE(?)
                          ORDER BY s.created_at DESC''', (start, end)).fetchall()
    receipts = db.execute('''SELECT r.id, r.created_at, i.name AS product_name, r.quantity_kg,
                             r.cost_price, r.selling_price, r.batch_number, r.expiration_date,
                             COALESCE(u.username, 'Deleted user') AS username
                             FROM stock_receipts r JOIN items i ON i.id = r.item_id
                             LEFT JOIN users u ON u.id = r.user_id
                             WHERE DATE(r.created_at) BETWEEN DATE(?) AND DATE(?)
                             ORDER BY r.created_at DESC''', (start, end)).fetchall()
    return jsonify({'start': start, 'end': end,
                    'sales': [dict(row) for row in sales],
                    'stock_receipts': [dict(row) for row in receipts]})


@app.route('/api/notifications', methods=['GET'])
@api_login_required
def list_notifications():
    db = get_db()
    refresh_notifications(db)
    rows = db.execute('SELECT id, kind, message, is_read, created_at FROM notifications ORDER BY is_read, created_at DESC LIMIT 50').fetchall()
    return jsonify([dict(row) for row in rows])


@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@api_login_required
def read_notification(notification_id):
    db = get_db()
    db.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))
    db.commit()
    return jsonify({'success': True})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Username and password required', 'danger')
            return render_template('login.html')
        
        db = get_db()
        cur = db.execute('SELECT id, username, password_hash, role, password_changed_at FROM users WHERE username = ?', (username,))
        user = cur.fetchone()
        
        print(f"[DEBUG LOGIN] Username: {username}", file=sys.stderr)
        print(f"[DEBUG LOGIN] User found: {user is not None}", file=sys.stderr)
        
        if user:
            print(f"[DEBUG LOGIN] User hash type: {type(user['password_hash'])}", file=sys.stderr)
            print(f"[DEBUG LOGIN] User hash: {user['password_hash'][:50]}", file=sys.stderr)
            result = verify_password(password, user['password_hash'])
            print(f"[DEBUG LOGIN] Password verify result: {result}", file=sys.stderr)
        
        if user and verify_password(password, user['password_hash']):
            session['user'] = username
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            
            print(f"[DEBUG LOGIN] Session set for user: {username}", file=sys.stderr)
            
            # Check if password has been changed; if not, redirect to force password change
            if user['password_changed_at'] is None:
                session['force_password_change'] = True
                flash('You must change your password on first login', 'warning')
                return redirect(url_for('change_password_forced'))
            
            flash('Logged in successfully', 'success')
            return redirect(url_for('home'))
        
        print(f"[DEBUG LOGIN] Login failed for user: {username}", file=sys.stderr)
        flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """Log out the user and clear the session."""
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))


@app.route('/change-password-forced', methods=['GET', 'POST'])
def change_password_forced():
    """Forced password change on first login."""
    # Require user to be logged in but bypass the force_password_change redirect check
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not new_password:
            flash('New password required', 'danger')
            return render_template('change_password_forced.html')
        if not confirm_password:
            flash('Confirm password required', 'danger')
            return render_template('change_password_forced.html')
        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('change_password_forced.html')
        if len(new_password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return render_template('change_password_forced.html')
        
        db = get_db()
        password_hash = hash_password(new_password)
        db.execute(
            'UPDATE users SET password_hash = ?, password_changed_at = CURRENT_TIMESTAMP WHERE id = ?',
            (password_hash, session.get('user_id'))
        )
        db.commit()
        
        # Clear the force password change flag
        session.pop('force_password_change', None)
        flash('Password changed successfully. You can now access the application.', 'success')
        return redirect(url_for('home'))
    
    return render_template('change_password_forced.html')




@app.route('/users')
@login_required
def users_page():
    """User Management page - admin only."""
    db = get_db()
    cur = db.execute('SELECT role FROM users WHERE username = ?', (session['user'],))
    user = cur.fetchone()
    
    if not user or user['role'] != 'admin':
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('home'))
    
    return render_template('users.html', user=session.get('user'))


@app.route('/backup-restore')
@login_required
def backup_restore_page():
    """Backup & Restore page - admin only."""
    db = get_db()
    cur = db.execute('SELECT role FROM users WHERE username = ?', (session['user'],))
    user = cur.fetchone()
    
    if not user or user['role'] != 'admin':
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('home'))
    
    return render_template('backup_restore.html', user=session.get('user'))


@app.route('/lists')
@login_required
def lists_page():
    return render_template('lists.html', user=session.get('user'))


@app.route('/shops')
@login_required
def shops_page():
    return render_template('shops.html', user=session.get('user'))


# ============= USER MANAGEMENT API ENDPOINTS =============

@app.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    """List all users. Admin only."""
    db = get_db()
    cur = db.execute('SELECT id, username, role, created_at FROM users ORDER BY created_at DESC')
    users = [dict(row) for row in cur.fetchall()]
    return jsonify(users)


@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    """Create a new user. Admin only."""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()
    role = data.get('role', 'normal').strip()
    
    # Validation
    if not username:
        return jsonify({'error': 'username required'}), 400
    if not password:
        return jsonify({'error': 'password required'}), 400
    if not confirm_password:
        return jsonify({'error': 'confirm_password required'}), 400
    if password != confirm_password:
        return jsonify({'error': 'passwords do not match'}), 400
    if role not in ['admin', 'normal']:
        return jsonify({'error': 'invalid role'}), 400
    if len(password) < 6:
        return jsonify({'error': 'password must be at least 6 characters'}), 400
    
    db = get_db()
    
    # Check for duplicate username
    cur = db.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cur.fetchone() is not None:
        return jsonify({'error': 'username already exists'}), 400
    
    # Hash password and create user
    password_hash = hash_password(password)
    cur = db.execute(
        'INSERT INTO users (username, password_hash, role, password_changed_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
        (username, password_hash, role)
    )
    db.commit()
    user_id = cur.lastrowid
    
    return jsonify({'id': user_id, 'username': username, 'role': role}), 201


@app.route('/api/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """Get user details. Admin only."""
    db = get_db()
    cur = db.execute('SELECT id, username, role, created_at FROM users WHERE id = ?', (user_id,))
    user = cur.fetchone()
    
    if user is None:
        return jsonify({'error': 'user not found'}), 404
    
    return jsonify(dict(user))


@app.route('/api/users/<int:user_id>/password', methods=['PUT'])
@admin_required
def change_user_password(user_id):
    """Change a user's password. Admin only."""
    data = request.get_json() or {}
    new_password = data.get('new_password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()
    
    # Validation
    if not new_password:
        return jsonify({'error': 'new_password required'}), 400
    if not confirm_password:
        return jsonify({'error': 'confirm_password required'}), 400
    if new_password != confirm_password:
        return jsonify({'error': 'passwords do not match'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'password must be at least 6 characters'}), 400
    
    db = get_db()
    
    # Verify user exists
    cur = db.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
    user = cur.fetchone()
    if user is None:
        return jsonify({'error': 'user not found'}), 404
    
    # Update password
    password_hash = hash_password(new_password)
    db.execute('UPDATE users SET password_hash = ?, password_changed_at = CURRENT_TIMESTAMP WHERE id = ?', (password_hash, user_id))
    db.commit()
    
    return jsonify({'success': True, 'message': f'Password updated for {user["username"]}'}), 200


@app.route('/api/users/<int:user_id>/role', methods=['PUT'])
@admin_required
def change_user_role(user_id):
    """Change a user's role. Admin only."""
    data = request.get_json() or {}
    new_role = data.get('role', '').strip()
    
    # Validation
    if new_role not in ['admin', 'normal']:
        return jsonify({'error': 'invalid role'}), 400
    
    db = get_db()
    
    # Verify user exists
    cur = db.execute('SELECT id, username, role FROM users WHERE id = ?', (user_id,))
    user = cur.fetchone()
    if user is None:
        return jsonify({'error': 'user not found'}), 404
    
    # Prevent removing the last admin
    if user['role'] == 'admin' and new_role != 'admin':
        cur = db.execute('SELECT COUNT(*) as admin_count FROM users WHERE role = ?', ('admin',))
        admin_count = cur.fetchone()['admin_count']
        if admin_count <= 1:
            return jsonify({'error': 'cannot remove the last administrator'}), 400
    
    # Update role
    db.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    db.commit()
    
    return jsonify({'success': True, 'message': f'Role updated for {user["username"]}'}), 200


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete a user. Admin only."""
    db = get_db()
    
    # Verify user exists
    cur = db.execute('SELECT id, username, role, is_default_admin FROM users WHERE id = ?', (user_id,))
    user = cur.fetchone()
    if user is None:
        return jsonify({'error': 'user not found'}), 404
    
    # Prevent deletion of the currently logged-in admin (check first - most specific)
    if session.get('user_id') == user_id:
        return jsonify({'error': 'cannot delete your own account'}), 400
    
    # Prevent deletion of the default admin account
    if user['is_default_admin']:
        return jsonify({'error': 'cannot delete the default admin account'}), 400
    
    # Prevent removing the last admin
    if user['role'] == 'admin':
        cur = db.execute('SELECT COUNT(*) as admin_count FROM users WHERE role = ?', ('admin',))
        admin_count = cur.fetchone()['admin_count']
        if admin_count <= 1:
            return jsonify({'error': 'cannot delete the last administrator'}), 400
    
    # Delete user
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()
    
    return jsonify({'success': True, 'message': f'User {user["username"]} deleted'}), 200


# ============= PRODUCT LISTS ENDPOINTS =============
@app.route('/api/lists', methods=['GET'])
@api_login_required
def list_product_lists():
    db = get_db()
    cur = db.execute('SELECT id, name, description, created_at FROM product_lists ORDER BY id DESC')
    lists = [dict(row) for row in cur.fetchall()]
    return jsonify(lists)


@app.route('/api/lists', methods=['POST'])
@api_login_required
def create_product_list():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    db = get_db()
    cur = db.execute('INSERT INTO product_lists (name, description) VALUES (?, ?)', (name, description))
    db.commit()
    list_id = cur.lastrowid
    return jsonify({'id': list_id, 'name': name, 'description': description}), 201


@app.route('/api/lists/<int:list_id>', methods=['GET'])
@api_login_required
def get_product_list(list_id):
    db = get_db()
    cur = db.execute('SELECT id, name, description, created_at FROM product_lists WHERE id = ?', (list_id,))
    list_row = cur.fetchone()
    if list_row is None:
        return jsonify({'error': 'not found'}), 404
    
    cur = db.execute('SELECT id, item_name, qty, cut_type, price FROM list_items WHERE list_id = ? ORDER BY id DESC', (list_id,))
    items = [dict(row) for row in cur.fetchall()]
    
    result = dict(list_row)
    result['items'] = items
    return jsonify(result)


@app.route('/api/lists/<int:list_id>', methods=['PUT'])
@api_login_required
def update_product_list(list_id):
    data = request.get_json() or {}
    name = data.get('name')
    description = data.get('description')
    db = get_db()
    cur = db.execute('SELECT id FROM product_lists WHERE id = ?', (list_id,))
    if cur.fetchone() is None:
        return jsonify({'error': 'not found'}), 404
    if name is not None:
        name = name.strip()
    if description is not None:
        description = description.strip()
    if all(v is None for v in [name, description]):
        return jsonify({'error': 'no fields to update'}), 400
    updates = []
    values = []
    if name is not None:
        updates.append('name = ?')
        values.append(name)
    if description is not None:
        updates.append('description = ?')
        values.append(description)
    values.append(list_id)
    query = f'UPDATE product_lists SET {", ".join(updates)} WHERE id = ?'
    db.execute(query, values)
    db.commit()
    cur = db.execute('SELECT id, name, description, created_at FROM product_lists WHERE id = ?', (list_id,))
    row = cur.fetchone()
    return jsonify(dict(row))


@app.route('/api/lists/<int:list_id>', methods=['DELETE'])
@api_login_required
def delete_product_list(list_id):
    db = get_db()
    cur = db.execute('SELECT id FROM product_lists WHERE id = ?', (list_id,))
    if cur.fetchone() is None:
        return jsonify({'error': 'not found'}), 404
    db.execute('DELETE FROM product_lists WHERE id = ?', (list_id,))
    db.commit()
    return '', 204


@app.route('/api/lists/<int:list_id>/items', methods=['POST'])
@api_login_required
def add_list_item(list_id):
    data = request.get_json() or {}
    item_name = data.get('item_name', '').strip()
    qty = data.get('qty', 1)
    cut_type = data.get('cut_type', '').strip()
    price = data.get('price')
    
    if not item_name:
        return jsonify({'error': 'item_name required'}), 400
    
    try:
        qty = int(qty)
        if qty < 0:
            return jsonify({'error': 'qty must be non-negative'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'invalid qty'}), 400
    
    if price is not None:
        try:
            price = float(price)
        except (ValueError, TypeError):
            return jsonify({'error': 'invalid price'}), 400
    
    db = get_db()
    
    # Check for duplicates (same item_name and cut_type combination)
    cur = db.execute(
        'SELECT id FROM list_items WHERE list_id = ? AND item_name = ? AND (cut_type = ? OR (cut_type IS NULL AND ? IS NULL))',
        (list_id, item_name, cut_type if cut_type else None, cut_type if cut_type else None)
    )
    if cur.fetchone() is not None:
        return jsonify({'error': 'product already exists in this list'}), 400
    
    cur = db.execute(
        'INSERT INTO list_items (list_id, item_name, qty, cut_type, price) VALUES (?, ?, ?, ?, ?)',
        (list_id, item_name, qty, cut_type if cut_type else None, price)
    )
    db.commit()
    item_id = cur.lastrowid
    return jsonify({'id': item_id, 'item_name': item_name, 'qty': qty, 'cut_type': cut_type, 'price': price}), 201


@app.route('/api/lists/<int:list_id>/items/<int:item_id>', methods=['PUT'])
@api_login_required
def update_list_item(list_id, item_id):
    data = request.get_json() or {}
    item_name = data.get('item_name')
    qty = data.get('qty')
    cut_type = data.get('cut_type')
    price = data.get('price')
    
    db = get_db()
    cur = db.execute('SELECT id FROM list_items WHERE id = ? AND list_id = ?', (item_id, list_id))
    if cur.fetchone() is None:
        return jsonify({'error': 'not found'}), 404
    
    if item_name is not None:
        item_name = item_name.strip()
    if cut_type is not None:
        cut_type = cut_type.strip()
    
    if all(v is None for v in [item_name, qty, cut_type, price]):
        return jsonify({'error': 'no fields to update'}), 400
    
    if qty is not None:
        try:
            qty = int(qty)
            if qty < 0:
                return jsonify({'error': 'qty must be non-negative'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'invalid qty'}), 400
    
    if price is not None:
        try:
            price = float(price)
        except (ValueError, TypeError):
            return jsonify({'error': 'invalid price'}), 400
    
    updates = []
    values = []
    if item_name is not None:
        updates.append('item_name = ?')
        values.append(item_name)
    if qty is not None:
        updates.append('qty = ?')
        values.append(qty)
    if cut_type is not None:
        updates.append('cut_type = ?')
        values.append(cut_type)
    if price is not None:
        updates.append('price = ?')
        values.append(price)
    values.append(item_id)
    values.append(list_id)
    query = f'UPDATE list_items SET {", ".join(updates)} WHERE id = ? AND list_id = ?'
    db.execute(query, values)
    db.commit()
    
    cur = db.execute('SELECT id, item_name, qty, cut_type, price FROM list_items WHERE id = ?', (item_id,))
    row = cur.fetchone()
    return jsonify(dict(row))


@app.route('/api/lists/<int:list_id>/items/<int:item_id>', methods=['DELETE'])
@api_login_required
def delete_list_item(list_id, item_id):
    db = get_db()
    cur = db.execute('SELECT id FROM list_items WHERE id = ? AND list_id = ?', (item_id, list_id))
    if cur.fetchone() is None:
        return jsonify({'error': 'not found'}), 404
    db.execute('DELETE FROM list_items WHERE id = ?', (item_id,))
    db.commit()
    return '', 204


@app.route('/api/items', methods=['GET'])
@api_login_required
def list_items():
    db = get_db()
    cur = db.execute('''
        SELECT i.id, i.name, i.shop_id, i.qty, i.cut_type, 
               li.price
        FROM items i
        LEFT JOIN list_items li ON li.item_name = i.name 
                                AND (li.cut_type = i.cut_type OR (li.cut_type IS NULL AND i.cut_type IS NULL))
        ORDER BY i.id DESC
    ''')
    items = []
    for row in cur.fetchall():
        # Try both named and indexed access
        try:
            row_dict = dict(row)
            price = row_dict.get('price')
        except Exception as e:
            price = None
        
        item = {
            'id': row['id'],
            'name': row['name'],
            'shop_id': row['shop_id'],
            'qty': row['qty'],
            'cut_type': row['cut_type'],
            'price': price
        }
        items.append(item)
    return jsonify(items)


@app.route('/api/items', methods=['POST'])
@api_login_required
def add_item():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    shop_id = data.get('shop_id')
    cut_type = data.get('cut_type', '').strip()
    try:
        qty = int(data.get('qty', 0))
        shop_id = int(shop_id)
    except Exception:
        return jsonify({'error': 'invalid data'}), 400
    if not name or qty < 0:
        return jsonify({'error': 'invalid input'}), 400
    db = get_db()
    cur = db.execute(
        'INSERT INTO items (name, shop_id, qty, cut_type) VALUES (?, ?, ?, ?)',
        (name, shop_id, qty, cut_type if cut_type else None)
    )
    db.commit()
    item_id = cur.lastrowid
    return jsonify({'id': item_id, 'name': name, 'shop_id': shop_id, 'qty': qty, 'cut_type': cut_type}), 201


@app.route('/api/items/<int:item_id>', methods=['GET'])
@api_login_required
def get_item(item_id):
    db = get_db()
    cur = db.execute('SELECT id, name, qty, cut_type FROM items WHERE id = ?', (item_id,))
    item = cur.fetchone()
    if item is None:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(item))


@app.route('/api/items/<int:item_id>', methods=['PUT'])
@api_login_required
def update_item(item_id):
    data = request.get_json() or {}
    qty = data.get('qty')
    db = get_db()
    cur = db.execute('SELECT id FROM items WHERE id = ?', (item_id,))
    if cur.fetchone() is None:
        return jsonify({'error': 'not found'}), 404
    if qty is None:
        return jsonify({'error': 'qty required'}), 400
    try:
        qty = int(qty)
        if qty < 0:
            return jsonify({'error': 'qty must be non-negative'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'invalid qty'}), 400
    db.execute('UPDATE items SET qty = ? WHERE id = ?', (qty, item_id))
    db.commit()
    cur = db.execute('SELECT id, name, qty, cut_type FROM items WHERE id = ?', (item_id,))
    row = cur.fetchone()
    return jsonify(dict(row))


@app.route('/api/items/<int:item_id>', methods=['DELETE'])
@api_login_required
def delete_item(item_id):
    db = get_db()
    cur = db.execute('SELECT id FROM items WHERE id = ?', (item_id,))
    if cur.fetchone() is None:
        return jsonify({'error': 'not found'}), 404
    db.execute('DELETE FROM items WHERE id = ?', (item_id,))
    db.commit()
    return '', 204


@app.route('/api/shops', methods=['GET'])
@api_login_required
def list_shops():
    db = get_db()
    cur = db.execute('SELECT id, name, location, phone, email, created_at FROM shops ORDER BY id DESC')
    shops = [dict(row) for row in cur.fetchall()]
    return jsonify(shops)


@app.route('/api/shops', methods=['POST'])
@api_login_required
def create_shop():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    location = data.get('location', '').strip()
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    db = get_db()
    cur = db.execute('INSERT INTO shops (name, location, phone, email) VALUES (?, ?, ?, ?)', (name, location, phone, email))
    db.commit()
    shop_id = cur.lastrowid
    return jsonify({'id': shop_id, 'name': name, 'location': location, 'phone': phone, 'email': email}), 201


@app.route('/api/shops/<int:shop_id>', methods=['GET'])
@api_login_required
def get_shop(shop_id):
    db = get_db()
    cur = db.execute('SELECT id, name, location, phone, email, created_at FROM shops WHERE id = ?', (shop_id,))
    shop = cur.fetchone()
    if shop is None:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(shop))


@app.route('/api/shops/<int:shop_id>', methods=['PUT'])
@api_login_required
def update_shop(shop_id):
    data = request.get_json() or {}
    name = data.get('name')
    location = data.get('location')
    phone = data.get('phone')
    email = data.get('email')
    db = get_db()
    cur = db.execute('SELECT id FROM shops WHERE id = ?', (shop_id,))
    if cur.fetchone() is None:
        return jsonify({'error': 'not found'}), 404
    if name is not None:
        name = name.strip()
    if location is not None:
        location = location.strip()
    if phone is not None:
        phone = phone.strip()
    if email is not None:
        email = email.strip()
    if all(v is None for v in [name, location, phone, email]):
        return jsonify({'error': 'no fields to update'}), 400
    updates = []
    values = []
    if name is not None:
        updates.append('name = ?')
        values.append(name)
    if location is not None:
        updates.append('location = ?')
        values.append(location)
    if phone is not None:
        updates.append('phone = ?')
        values.append(phone)
    if email is not None:
        updates.append('email = ?')
        values.append(email)
    values.append(shop_id)
    query = f'UPDATE shops SET {", ".join(updates)} WHERE id = ?'
    db.execute(query, values)
    db.commit()
    cur = db.execute('SELECT id, name, location, phone, email, created_at FROM shops WHERE id = ?', (shop_id,))
    row = cur.fetchone()
    return jsonify(dict(row))


@app.route('/api/shops/<int:shop_id>', methods=['DELETE'])
@api_login_required
def delete_shop(shop_id):
    db = get_db()
    cur = db.execute('SELECT id FROM shops WHERE id = ?', (shop_id,))
    if cur.fetchone() is None:
        return jsonify({'error': 'not found'}), 404
    db.execute('DELETE FROM shops WHERE id = ?', (shop_id,))
    db.commit()
    return '', 204


@app.route('/api/transfer', methods=['POST'])
@api_login_required
def transfer_stock():
    """Transfer stock of a product between shops.
    
    Expected JSON body:
    {
       "product_name": "Product Name",
       "from_shop_id": 1,
       "to_shop_id": 2,
       "quantity": 5
    }
    """
    data = request.get_json() or {}
    product_name = data.get('product_name')
    from_shop_id = data.get('from_shop_id')
    to_shop_id = data.get('to_shop_id')
    qty = data.get('quantity')
    
    # Validate inputs
    if not product_name or from_shop_id is None or to_shop_id is None or qty is None:
       return jsonify({'error': 'Missing required fields'}), 400
    
    try:
       from_shop_id = int(from_shop_id)
       to_shop_id = int(to_shop_id)
       qty = int(qty)
    except (ValueError, TypeError):
       return jsonify({'error': 'Invalid data types'}), 400
    
    if qty <= 0:
       return jsonify({'error': 'Quantity must be positive'}), 400
    
    if from_shop_id == to_shop_id:
       return jsonify({'error': 'Cannot transfer to the same shop'}), 400
    
    db = get_db()
    
    # Find the source item by product name and shop
    cur = db.execute(
       'SELECT id, qty, cut_type FROM items WHERE name = ? AND shop_id = ?',
       (product_name, from_shop_id)
    )
    source_item = cur.fetchone()
    
    if source_item is None:
       return jsonify({'error': 'Product not found in source shop'}), 404
    
    if source_item['qty'] < qty:
       return jsonify({'error': f'Insufficient quantity. Available: {source_item["qty"]}'}), 400
    
    try:
       # Deduct from source shop
       db.execute('UPDATE items SET qty = qty - ? WHERE id = ?', (qty, source_item['id']))
        
       # Check if product exists in destination shop with same cut_type
       cur = db.execute(
           'SELECT id FROM items WHERE name = ? AND shop_id = ? AND cut_type = ?',
           (product_name, to_shop_id, source_item['cut_type'])
       )
       dest_item = cur.fetchone()
        
       if dest_item:
           # Add to existing destination item
           db.execute('UPDATE items SET qty = qty + ? WHERE id = ?', (qty, dest_item['id']))
       else:
           # Create new item in destination shop
           db.execute(
               'INSERT INTO items (name, shop_id, qty, cut_type) VALUES (?, ?, ?, ?)',
               (product_name, to_shop_id, qty, source_item['cut_type'])
           )
        
       db.commit()
       return jsonify({
           'success': True,
           'message': f'Transferred {qty} units from shop {from_shop_id} to shop {to_shop_id}'
       }), 200
    
    except Exception as e:
       db.rollback()
       return jsonify({'error': f'Transfer failed: {str(e)}'}), 500


@app.route('/api/items/<int:item_id>/transfer', methods=['POST'])
@api_login_required
def transfer_item(item_id):
    data = request.get_json() or {}
    to_shop_id = data.get('to_shop_id')
    qty = data.get('qty', 1)
    try:
        to_shop_id = int(to_shop_id)
        qty = int(qty)
    except Exception:
        return jsonify({'error': 'invalid data'}), 400
    if qty <= 0:
        return jsonify({'error': 'qty must be positive'}), 400
    db = get_db()
    cur = db.execute('SELECT id, name, shop_id, qty, cut_type FROM items WHERE id = ?', (item_id,))
    item = cur.fetchone()
    if item is None:
        return jsonify({'error': 'item not found'}), 404
    if item['qty'] < qty:
        return jsonify({'error': 'insufficient qty'}), 400
    # Deduct from source
    db.execute('UPDATE items SET qty = qty - ? WHERE id = ?', (qty, item_id))
    # Check if item exists in destination with same name and cut_type
    cur = db.execute(
        'SELECT id, qty FROM items WHERE name = ? AND shop_id = ? AND cut_type = ?',
        (item['name'], to_shop_id, item['cut_type'])
    )
    dest_item = cur.fetchone()
    if dest_item:
        db.execute('UPDATE items SET qty = qty + ? WHERE id = ?', (qty, dest_item['id']))
    else:
        db.execute(
            'INSERT INTO items (name, shop_id, qty, cut_type) VALUES (?, ?, ?, ?)',
            (item['name'], to_shop_id, qty, item['cut_type'])
        )
    db.commit()
    return jsonify({'success': True}), 200


# ============= BACKUP & RESTORE ENDPOINTS =============

def export_database_to_json(db):
    """Export database to JSON format for portable backup."""
    backup_data = {
        'format': 'inventory_backup',
        'format_version': 2,
        'created_at': datetime.now().isoformat(),
        'tables': {}
    }
    
    # Export all tables
    tables = ['users', 'shops', 'product_lists', 'list_items', 'items', 'stock_receipts', 'sales', 'notifications']
    for table in tables:
        try:
            cur = db.execute(f'SELECT * FROM {table}')
            columns = [description[0] for description in cur.description]
            rows = cur.fetchall()
            backup_data['tables'][table] = {
                'columns': columns,
                'rows': [dict(row) for row in rows] if rows else []
            }
        except Exception as e:
            # Table might not exist in older versions
            backup_data['tables'][table] = {'columns': [], 'rows': []}
    
    return backup_data


def create_backup_zip():
    """Create a backup ZIP file in memory."""
    db = get_db()
    
    # Export database to JSON
    backup_data = export_database_to_json(db)
    
    # Create ZIP in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Write metadata
        metadata = {
            'backup_format_version': 2,
            'application_version': '2.0.0',
            'database_schema_version': 6,
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        zf.writestr('BACKUP_INFO.json', json.dumps(metadata, indent=2))
        
        # Write database export
        zf.writestr('database.json', json.dumps(backup_data, indent=2, default=str))
    
    zip_buffer.seek(0)
    return zip_buffer


@app.route('/api/backup/create', methods=['POST'])
@admin_required
def create_backup():
    """Create and download database backup. Admin only."""
    try:
        zip_buffer = create_backup_zip()
        timestamp = datetime.now().strftime('%Y-%m-%d-%H%M')
        filename = f'app-backup-{timestamp}.zip'
        
        # Log backup creation
        db = get_db()
        db.execute(
            'INSERT INTO backup_log (operation, status, user_id, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
            ('create', 'success', session.get('user_id'))
        )
        db.commit()
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        db = get_db()
        db.execute(
            'INSERT INTO backup_log (operation, status, user_id, error_message, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
            ('create', 'failed', session.get('user_id'), str(e))
        )
        db.commit()
        return jsonify({'error': f'Backup creation failed: {str(e)}'}), 500


def validate_backup_zip(zip_buffer):
    """Validate backup ZIP file structure and contents."""
    try:
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            # Check required files exist
            if 'BACKUP_INFO.json' not in zf.namelist():
                return False, 'Missing BACKUP_INFO.json'
            if 'database.json' not in zf.namelist():
                return False, 'Missing database.json'
            
            # Validate BACKUP_INFO.json
            try:
                info = json.loads(zf.read('BACKUP_INFO.json').decode('utf-8'))
                if 'backup_format_version' not in info:
                    return False, 'Invalid BACKUP_INFO.json format'
            except Exception as e:
                return False, f'Failed to parse BACKUP_INFO.json: {str(e)}'
            
            # Validate database.json
            try:
                db_data = json.loads(zf.read('database.json').decode('utf-8'))
                if db_data.get('format') != 'inventory_backup':
                    return False, 'Invalid backup format'
                if 'tables' not in db_data:
                    return False, 'Missing tables data'
            except Exception as e:
                return False, f'Failed to parse database.json: {str(e)}'
        
        return True, 'Backup valid'
    except zipfile.BadZipFile:
        return False, 'Invalid ZIP file'
    except Exception as e:
        return False, f'Validation error: {str(e)}'


def restore_from_backup(zip_buffer):
    """Restore database from backup ZIP file."""
    db = None
    try:
        # Validate backup first
        is_valid, message = validate_backup_zip(zip_buffer)
        if not is_valid:
            return False, message
        
        # Extract backup data
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            db_data = json.loads(zf.read('database.json').decode('utf-8'))
        
        db = get_db()
        
        # Get list of tables to clear (includes users now)
        # Delete in order of foreign key dependencies
        tables_to_clear = ['notifications', 'sales', 'stock_receipts', 'items', 'list_items', 'product_lists', 'shops', 'users']
        
        # Clear existing data (but preserve backup_log)
        # Delete in order to avoid foreign key constraint violations
        for table in tables_to_clear:
            try:
                db.execute(f'DELETE FROM {table}')
                # Keep the entire restore atomic; commit only after every table is restored.
            except Exception as e:
                raise RuntimeError(f'Could not clear {table}: {e}') from e
        
        # Restore all tables except backup_log
        allowed_tables = {'users', 'shops', 'product_lists', 'list_items', 'items', 'stock_receipts', 'sales', 'notifications'}
        tables_to_restore = [t for t in db_data.get('tables', {}).keys() if t in allowed_tables]
        
        restore_errors = []  # Track errors for debugging
        
        for table_name in tables_to_restore:
            table_data = db_data['tables'][table_name]
            rows = table_data.get('rows', [])
            
            if not rows:
                continue  # Skip empty tables
            
            # Get columns from first row
            columns = table_data.get('columns', [])
            
            # Filter out ID column for insertion (it will be auto-generated)
            # Actually, keep ID for data integrity
            for i, row in enumerate(rows):
                placeholders = ','.join(['?' for _ in columns])
                values = [row.get(col) for col in columns]
                try:
                    db.execute(
                        f'INSERT INTO {table_name} ({",".join(columns)}) VALUES ({placeholders})',
                        values
                    )
                except Exception as e:
                    error_msg = f'Table {table_name}, row {i}: {type(e).__name__}: {e}'
                    restore_errors.append(error_msg)
                    raise RuntimeError(error_msg) from e
        
        db.commit()
        # PostgreSQL sequences are not advanced by explicit IDs from a backup.
        # Re-sync them so the next normal insert cannot collide with restored data.
        if USE_POSTGRES:
            for table_name in allowed_tables:
                db.execute(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), COALESCE((SELECT MAX(id) FROM {table_name}), 1), true)")
            db.commit()
        
        # Print errors if any (for debugging)
        if restore_errors:
            print(f"[RESTORE] Warning: {len(restore_errors)} errors during restore:")
            for error in restore_errors[:10]:  # Print first 10 errors
                print(f"  - {error}")
        
        return True, 'Database restored successfully'
    
    except Exception as e:
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        return False, f'Restoration failed: {str(e)}'


@app.route('/api/backup/restore', methods=['POST'])
@admin_required
def restore_backup():
    """Restore database from uploaded backup file. Admin only."""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.zip'):
            return jsonify({'error': 'File must be a ZIP archive'}), 400
        
        # Read file into buffer
        file_data = file.read()
        zip_buffer = BytesIO(file_data)
        
        # Validate backup
        is_valid, message = validate_backup_zip(zip_buffer)
        if not is_valid:
            db = get_db()
            db.execute(
                'INSERT INTO backup_log (operation, status, user_id, error_message, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
                ('restore', 'failed', session.get('user_id'), f'Validation failed: {message}')
            )
            db.commit()
            return jsonify({'error': f'Invalid backup: {message}'}), 400
        
        # Restore backup
        zip_buffer.seek(0)
        success, message = restore_from_backup(zip_buffer)
        
        # Log restore attempt
        db = get_db()
        db.execute(
            'INSERT INTO backup_log (operation, status, user_id, backup_metadata, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
            ('restore', 'success' if success else 'failed', session.get('user_id'), message)
        )
        db.commit()
        
        if not success:
            return jsonify({'error': message}), 500
        
        return jsonify({'success': True, 'message': message}), 200
    
    except Exception as e:
        db = get_db()
        db.execute(
            'INSERT INTO backup_log (operation, status, user_id, error_message, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
            ('restore', 'failed', session.get('user_id'), str(e))
        )
        db.commit()
        return jsonify({'error': f'Restore failed: {str(e)}'}), 500


@app.route('/api/backup/info', methods=['POST'])
@admin_required
def get_backup_info():
    """Get information about a backup file. Admin only."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.zip'):
            return jsonify({'error': 'File must be a ZIP archive'}), 400
        
        file_data = file.read()
        zip_buffer = BytesIO(file_data)
        
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            info = json.loads(zf.read('BACKUP_INFO.json').decode('utf-8'))
            db_data = json.loads(zf.read('database.json').decode('utf-8'))
            
            # Count records
            record_counts = {}
            for table, data in db_data.get('tables', {}).items():
                record_counts[table] = len(data.get('rows', []))
            
            return jsonify({
                'backup_format_version': info.get('backup_format_version'),
                'application_version': info.get('application_version'),
                'database_schema_version': info.get('database_schema_version'),
                'created': info.get('created'),
                'record_counts': record_counts
            }), 200
    except Exception as e:
        return jsonify({'error': f'Failed to read backup info: {str(e)}'}), 400


if __name__ == '__main__':
    # Only run Flask development server if explicitly in development mode
    # In production (Docker), use Gunicorn via entrypoint.sh
    if FLASK_ENV == 'development':
        app.run(debug=FLASK_DEBUG, host='0.0.0.0', port=5000)
    else:
        # Production mode: print notice and exit
        print("ERROR: Flask development server should not be used in production.")
        print("This application should be run with Gunicorn via Docker or with:")
        print("  gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app")
        sys.exit(1)
