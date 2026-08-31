# Database Adapter for both SQLite and PostgreSQL
# This module provides a unified database interface for app.py

import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

USE_POSTGRES = os.environ.get('DB_HOST') is not None

class DatabaseAdapter:
    """Unified database interface for SQLite and PostgreSQL"""
    
    def __init__(self):
        self.use_postgres = USE_POSTGRES
        self.conn = None
        self.postgres_conn = None
    
    def connect(self):
        """Connect to appropriate database based on environment"""
        if self.use_postgres:
            self._connect_postgres()
        else:
            self._connect_sqlite()
        return self.conn
    
    def _connect_sqlite(self):
        """Connect to SQLite database"""
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_DIR = os.path.join(BASE_DIR, 'instance')
        DB_PATH = os.path.join(DB_DIR, 'inventory.db')
        
        os.makedirs(DB_DIR, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
    
    def _connect_postgres(self):
        """Connect to PostgreSQL database"""
        self.conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=os.environ.get('DB_PORT', '5432'),
            database=os.environ.get('DB_NAME', 'inventory'),
            user=os.environ.get('DB_USER', 'inventory_app'),
            password=os.environ.get('DB_PASSWORD', '')
        )
        self.postgres_conn = self.conn
        self.conn.row_factory = RealDictCursor
    
    def execute(self, query, params=None):
        """Execute query and return cursor-like object"""
        if self.use_postgres:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
        else:
            cursor = self.conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
    
    def execute_and_commit(self, query, params=None):
        """Execute query and commit"""
        cursor = self.execute(query, params)
        self.conn.commit()
        return cursor
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None


def init_postgres_schema():
    """Initialize PostgreSQL schema if using PostgreSQL"""
    if not USE_POSTGRES:
        return
    
    # Read and execute init-db.sql
    sql_file = os.path.join(os.path.dirname(__file__), 'init-db.sql')
    if os.path.exists(sql_file):
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Replace environment variable placeholders
        sql_content = sql_content.replace(
            '${DB_USER:-inventory_app}',
            os.environ.get('DB_USER', 'inventory_app')
        )
        
        db = DatabaseAdapter()
        db.connect()
        
        # Split by statements and execute
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        for statement in statements:
            try:
                db.execute_and_commit(statement)
            except Exception as e:
                print(f"Warning executing statement: {e}")
        
        db.close()
