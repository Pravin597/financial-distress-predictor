import os
import sqlite3
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = 'data/financials.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """
    Creates tables in SQLite if they do not already exist and runs migrations.
    """
    os.makedirs('data', exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # 2. Companies table (scoped to a user)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(name, user_id)
        )
    ''')
    
    # 3. Financial records table (scoped to a company)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS financial_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            cash_flow REAL NOT NULL,
            profit REAL NOT NULL,
            expenses REAL NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE,
            UNIQUE(company_id, date)
        )
    ''')
    
    # Run Schema Migrations:
    # A. Check and add 'ca_notes' column to companies table
    cursor.execute("PRAGMA table_info(companies)")
    companies_cols = [row['name'] for row in cursor.fetchall()]
    if 'ca_notes' not in companies_cols:
        cursor.execute("ALTER TABLE companies ADD COLUMN ca_notes TEXT DEFAULT ''")
        print("Migration: Added 'ca_notes' column to 'companies' table.")
        
    # B. Check and add 'loans' column to financial_records table
    cursor.execute("PRAGMA table_info(financial_records)")
    records_cols = [row['name'] for row in cursor.fetchall()]
    if 'loans' not in records_cols:
        cursor.execute("ALTER TABLE financial_records ADD COLUMN loans REAL DEFAULT 0.0")
        print("Migration: Added 'loans' column to 'financial_records' table.")

    # C. Check and add 'currency' column to companies table
    cursor.execute("PRAGMA table_info(companies)")
    companies_cols = [row['name'] for row in cursor.fetchall()]
    if 'currency' not in companies_cols:
        cursor.execute("ALTER TABLE companies ADD COLUMN currency TEXT DEFAULT '$'")
        print("Migration: Added 'currency' column to 'companies' table.")
        
    # D. Check and add 'is_admin' column to users table
    cursor.execute("PRAGMA table_info(users)")
    users_cols = [row['name'] for row in cursor.fetchall()]
    if 'is_admin' not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        print("Migration: Added 'is_admin' column to 'users' table.")
        
    # E. Seed admin user if not exists
    cursor.execute("SELECT id FROM users WHERE username = 'admin_user'")
    if not cursor.fetchone():
        admin_pass = generate_password_hash('admin123')
        cursor.execute(
            'INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)',
            ('admin_user', admin_pass)
        )
        print("Migration: Seeded default admin_user with password 'admin123'.")

    # F. Check and add calculated forecast columns to companies
    cursor.execute("PRAGMA table_info(companies)")
    companies_cols = [row['name'] for row in cursor.fetchall()]
    if 'last_distress_score' not in companies_cols:
        cursor.execute("ALTER TABLE companies ADD COLUMN last_distress_score REAL")
        cursor.execute("ALTER TABLE companies ADD COLUMN last_distress_status TEXT")
        cursor.execute("ALTER TABLE companies ADD COLUMN last_calculated_date TIMESTAMP")
        print("Migration: Added calculated forecast columns to 'companies' table.")

    # G. Check and add silent web data columns to companies
    if 'web_summary' not in companies_cols:
        cursor.execute("ALTER TABLE companies ADD COLUMN web_summary TEXT")
        cursor.execute("ALTER TABLE companies ADD COLUMN web_stock_trend TEXT")
        print("Migration: Added silent web data columns to 'companies' table.")
    conn.commit()
    conn.close()
    print("Database tables and migrations initialized successfully!")

# ================= AUTHENTICATION =================

def create_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)
    try:
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return {'id': user_id, 'username': username}
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def verify_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        is_admin = bool(user['is_admin']) if 'is_admin' in user.keys() else False
        return {'id': user['id'], 'username': user['username'], 'is_admin': is_admin}
    return None

# ================= COMPANIES (CRUD) =================

def create_company(name, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO companies (name, user_id) VALUES (?, ?)',
            (name, user_id)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_companies_by_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM companies WHERE user_id = ? ORDER BY name', (user_id,))
    companies = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return companies

def verify_company_ownership(company_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM companies WHERE id = ? AND user_id = ?', (company_id, user_id))
    owned = cursor.fetchone() is not None
    if not owned:
        print(f"Ownership check failed for company {company_id}, user {user_id}")
    conn.close()
    return owned

def delete_company(company_id, user_id):
    if not verify_company_ownership(company_id, user_id):
        return False
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM financial_records WHERE company_id = ?', (company_id,))
    cursor.execute('DELETE FROM companies WHERE id = ?', (company_id,))
    conn.commit()
    conn.close()
    return True

def rename_company(company_id, user_id, new_name):
    if not verify_company_ownership(company_id, user_id):
        return False
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE companies SET name = ? WHERE id = ?', (new_name, company_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        print(f"Rename IntegrityError for {new_name}, id {company_id}: {e}")
        return False
    finally:
        conn.close()

def update_company_currency(company_id, user_id, currency):
    if not verify_company_ownership(company_id, user_id):
        return False
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE companies SET currency = ? WHERE id = ?', (currency, company_id))
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()

# ================= CA SHEET NOTES =================

def get_ca_sheet(company_id, user_id):
    if not verify_company_ownership(company_id, user_id):
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT ca_notes FROM companies WHERE id = ?', (company_id,))
    row = cursor.fetchone()
    conn.close()
    return row['ca_notes'] if row else ""

def save_ca_sheet(company_id, user_id, notes):
    if not verify_company_ownership(company_id, user_id):
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE companies SET ca_notes = ? WHERE id = ?', (notes, company_id))
    conn.commit()
    conn.close()
    return True

def update_company_forecast(company_id, user_id, score, status, web_summary=None, web_trend=None):
    if not verify_company_ownership(company_id, user_id):
        return False
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE companies 
        SET last_distress_score = ?, last_distress_status = ?, last_calculated_date = CURRENT_TIMESTAMP,
            web_summary = COALESCE(?, web_summary), web_stock_trend = COALESCE(?, web_stock_trend)
        WHERE id = ?
    ''', (score, status, web_summary, web_trend, company_id))
    conn.commit()
    conn.close()
    return True

# ================= FINANCIAL RECORDS (CRUD) =================

def get_records_by_company(company_id, user_id):
    if not verify_company_ownership(company_id, user_id):
        return None
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM financial_records WHERE company_id = ? ORDER BY date ASC',
        (company_id,)
    )
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return records

def add_record(company_id, user_id, date, cash_flow, profit, expenses, loans=0.0):
    if not verify_company_ownership(company_id, user_id):
        return None
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''INSERT INTO financial_records (company_id, date, cash_flow, profit, expenses, loans) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (company_id, date, cash_flow, profit, expenses, loans)
        )
        conn.commit()
        record_id = cursor.lastrowid
        return record_id
    except sqlite3.IntegrityError:
        cursor.execute(
            '''UPDATE financial_records 
               SET cash_flow = ?, profit = ?, expenses = ?, loans = ? 
               WHERE company_id = ? AND date = ?''',
            (cash_flow, profit, expenses, loans, company_id, date)
        )
        conn.commit()
        return "UPDATED"
    finally:
        conn.close()

def update_record(record_id, user_id, date, cash_flow, profit, expenses, loans=0.0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT r.company_id FROM financial_records r 
           JOIN companies c ON r.company_id = c.id 
           WHERE r.id = ? AND c.user_id = ?''',
        (record_id, user_id)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
        
    try:
        cursor.execute(
            '''UPDATE financial_records 
               SET date = ?, cash_flow = ?, profit = ?, expenses = ?, loans = ? 
               WHERE id = ?''',
            (date, cash_flow, profit, expenses, loans, record_id)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_record(record_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT r.id FROM financial_records r 
           JOIN companies c ON r.company_id = c.id 
           WHERE r.id = ? AND c.user_id = ?''',
        (record_id, user_id)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
        
    cursor.execute('DELETE FROM financial_records WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()
    return True

# ================= ADMIN QUERIES =================

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, is_admin FROM users ORDER BY id')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def get_all_companies():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.*, u.username as owner_username 
        FROM companies c 
        JOIN users u ON c.user_id = u.id 
        ORDER BY c.id
    ''')
    companies = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return companies


