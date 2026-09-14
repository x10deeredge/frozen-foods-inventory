from flask import Flask, render_template, request, jsonify, session, make_response, send_file, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import io
import json
from datetime import datetime, timedelta, date
from functools import wraps
import pdf_generator

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'pandas_erp_wholesale_secret_2026_super_secure')
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'inventory.db'))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            business_name TEXT DEFAULT "PANDA'S Wholesale Distribution System",
            address TEXT DEFAULT '',
            tax_id TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            currency TEXT DEFAULT 'PKR',
            role TEXT DEFAULT 'Owner / Executive',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sku TEXT DEFAULT '',
            category TEXT NOT NULL,
            unit TEXT NOT NULL,
            batch_no TEXT DEFAULT '',
            expiry_date TEXT DEFAULT '',
            storage_loc TEXT DEFAULT '',
            brand TEXT DEFAULT '',
            description TEXT DEFAULT '',
            min_order_qty REAL DEFAULT 0,
            low_stock_threshold REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stock_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            total_cost REAL NOT NULL,
            supplier TEXT DEFAULT '',
            purchase_date DATE NOT NULL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            invoice_no TEXT DEFAULT '',
            client_name TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            quantity_sold REAL NOT NULL,
            unit_price REAL DEFAULT 0,
            total_amount REAL NOT NULL,
            sale_date DATE NOT NULL,
            payment_status TEXT DEFAULT 'Paid',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            expense_date DATE NOT NULL,
            category TEXT DEFAULT '',
            payment_method TEXT DEFAULT 'Cash',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()

    migrations = [
        "ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN address TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN tax_id TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'Owner / Executive'",
        "ALTER TABLE users ADD COLUMN bank_details TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN invoice_notes TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN user_id INTEGER DEFAULT 1",
        "ALTER TABLE products ADD COLUMN sku TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN batch_no TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN expiry_date TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN storage_loc TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN brand TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN description TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN min_order_qty REAL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN low_stock_threshold REAL DEFAULT 0",
        "ALTER TABLE stock_entries ADD COLUMN user_id INTEGER DEFAULT 1",
        "ALTER TABLE stock_entries ADD COLUMN supplier TEXT DEFAULT ''",
        "ALTER TABLE sales ADD COLUMN user_id INTEGER DEFAULT 1",
        "ALTER TABLE sales ADD COLUMN invoice_no TEXT DEFAULT ''",
        "ALTER TABLE sales ADD COLUMN unit_price REAL DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN payment_status TEXT DEFAULT 'Paid'",
        "ALTER TABLE expenses ADD COLUMN user_id INTEGER DEFAULT 1",
        "ALTER TABLE expenses ADD COLUMN payment_method TEXT DEFAULT 'Cash'",
    ]
    for sql in migrations:
        try:
            c.execute(sql)
            conn.commit()
        except Exception:
            pass

    # Clean up empty emails to NULL so SQLite UNIQUE allows multiple accounts without email
    try:
        c.execute("UPDATE users SET email = NULL WHERE email = ''")
        conn.commit()
    except Exception:
        pass

    # Ensure demo user exists
    admin = c.execute('SELECT * FROM users WHERE id=1').fetchone()
    if not admin:
        default_hash = generate_password_hash('panda123')
        c.execute('''
            INSERT INTO users (id, username, email, password_hash, full_name, business_name, address, tax_id, phone, role)
            VALUES (1, 'panda_admin', 'admin@pandas.com', ?, 'Bilal Ahmed', "PANDA'S Wholesale Distribution System", 'Main Cold Chain Complex, Sector 7, Karachi', 'NTN-893421-9', '+92 300 8291024', 'Managing Director')
        ''', (default_hash,))
        conn.commit()

    conn.close()


def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized. Please login to continue.', 'auth_required': True}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_current_user_id():
    return session.get('user_id')


def generate_invoice_no(cursor, uid):
    last = cursor.execute('SELECT invoice_no FROM sales WHERE user_id=? AND invoice_no != "" ORDER BY id DESC LIMIT 1', (uid,)).fetchone()
    if last and last[0] and last[0].startswith('PND-INV-'):
        try:
            num = int(last[0].split('-')[-1]) + 1
            return f"PND-INV-{num:04d}"
        except Exception:
            pass
    count = cursor.execute('SELECT COUNT(DISTINCT invoice_no) FROM sales WHERE user_id=? AND invoice_no != ""', (uid,)).fetchone()[0]
    return f"PND-INV-{count + 1001:04d}"


def get_date_range_filter(period, start_date=None, end_date=None):
    today = datetime.now().date()
    if period == 'today':
        return today.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    elif period == 'this_week':
        start = today - timedelta(days=today.weekday())
        return start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    elif period == 'this_month':
        start = today.replace(day=1)
        return start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    elif period == 'last_month':
        first_this = today.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start.strftime('%Y-%m-%d'), last_month_end.strftime('%Y-%m-%d')
    elif period == 'this_year':
        start = today.replace(month=1, day=1)
        return start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    elif period == 'custom' and start_date and end_date:
        return start_date, end_date
    return None, None  # All time


# ── ROOT ───────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/manifest.json')
def root_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')


@app.route('/sw.js')
def root_sw():
    response = send_from_directory('static', 'sw.js', mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    return response


# ── REAL AUTHENTICATION & MULTI-USER ───────────────────────────────────────────
@app.route('/api/auth/me')
def api_auth_me():
    uid = get_current_user_id()
    if not uid:
        return jsonify({'logged_in': False, 'user': None})

    conn = get_db()
    user = conn.execute('SELECT id, username, email, full_name, business_name, address, tax_id, phone, currency, role, bank_details, invoice_notes, created_at FROM users WHERE id=?', (uid,)).fetchone()
    conn.close()
    if user:
        return jsonify({'logged_in': True, 'user': dict(user)})
    return jsonify({'logged_in': False, 'user': None})


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'Please enter both username/email and password'}), 400

    conn = get_db()
    # Support login with either username or email
    user = conn.execute('''
        SELECT * FROM users 
        WHERE LOWER(username)=LOWER(?) 
           OR (email IS NOT NULL AND email != '' AND LOWER(email)=LOWER(?))
    ''', (username, username)).fetchone()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid username/email or password. Please try again.'}), 401

    session.permanent = True
    session['user_id'] = user['id']
    session['username'] = user['username']

    user_dict = dict(user)
    user_dict.pop('password_hash', None)
    return jsonify({'success': True, 'user': user_dict})


@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    full_name = data.get('full_name', '').strip()
    business_name = data.get('business_name', '').strip() or (full_name if full_name else f"{username.capitalize()} Wholesale Store")
    address = data.get('address', '').strip()
    phone = data.get('phone', '').strip()

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    if len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters long'}), 400

    conn = get_db()
    exists = conn.execute('SELECT id FROM users WHERE LOWER(username)=LOWER(?)', (username,)).fetchone()
    if exists:
        conn.close()
        return jsonify({'error': f'Username "{username}" is already taken. Please choose a different username.'}), 400

    # Email handling: validate uniqueness if provided, else store as None (SQL NULL)
    # In SQLite, multiple NULL values are allowed for UNIQUE columns, but multiple '' violate UNIQUE!
    if email:
        email_exists = conn.execute('SELECT id FROM users WHERE LOWER(email)=LOWER(?)', (email,)).fetchone()
        if email_exists:
            conn.close()
            return jsonify({'error': f'Email "{email}" is already registered. Please log in or use another email address.'}), 400
    else:
        email = None

    password_hash = generate_password_hash(password)
    try:
        conn.execute('''
            INSERT INTO users (username, email, password_hash, full_name, business_name, address, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, email, password_hash, full_name, business_name, address, phone))
        conn.commit()
        uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()

        session.permanent = True
        session['user_id'] = uid
        session['username'] = username

        return jsonify({'success': True, 'user_id': uid, 'username': username}), 201
    except sqlite3.IntegrityError as ie:
        conn.close()
        err_str = str(ie).lower()
        if 'users.username' in err_str:
            return jsonify({'error': f'Username "{username}" is already taken.'}), 400
        elif 'users.email' in err_str:
            return jsonify({'error': f'Email "{email}" is already registered. Please use another email.'}), 400
        return jsonify({'error': 'An account with this information already exists.'}), 400
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/auth/profile', methods=['PUT'])
@auth_required
def api_auth_profile():
    uid = get_current_user_id()
    data = request.get_json() or {}

    email = data.get('email', '').strip()
    full_name = data.get('full_name', '').strip()
    business_name = data.get('business_name', '').strip() or (full_name if full_name else 'Wholesale Store')
    address = data.get('address', '').strip()
    tax_id = data.get('tax_id', '').strip()
    phone = data.get('phone', '').strip()
    currency = data.get('currency', '').strip() or 'PKR'
    role = data.get('role', '').strip() or 'Owner'

    conn = get_db()
    if email:
        exists = conn.execute('SELECT id FROM users WHERE LOWER(email)=LOWER(?) AND id!=?', (email, uid)).fetchone()
        if exists:
            conn.close()
            return jsonify({'error': f'Email "{email}" is already used by another account.'}), 400
    else:
        email = None

    bank_details = data.get('bank_details', '').strip()
    invoice_notes = data.get('invoice_notes', '').strip()

    conn.execute('''
        UPDATE users SET email=?, full_name=?, business_name=?, address=?, tax_id=?, phone=?, currency=?, role=?, bank_details=?, invoice_notes=?
        WHERE id=?
    ''', (email, full_name, business_name, address, tax_id, phone, currency, role, bank_details, invoice_notes, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/auth/change-password', methods=['PUT'])
@auth_required
def api_auth_change_password():
    uid = get_current_user_id()
    data = request.get_json() or {}
    old_password = data.get('old_password', '').strip()
    new_password = data.get('new_password', '').strip()

    if not old_password or not new_password:
        return jsonify({'error': 'Old and new passwords are required'}), 400

    if len(new_password) < 4:
        return jsonify({'error': 'New password must be at least 4 characters'}), 400

    conn = get_db()
    user = conn.execute('SELECT password_hash FROM users WHERE id=?', (uid,)).fetchone()
    if not user or not check_password_hash(user['password_hash'], old_password):
        conn.close()
        return jsonify({'error': 'Current password is incorrect'}), 400

    new_hash = generate_password_hash(new_password)
    conn.execute('UPDATE users SET password_hash=? WHERE id=?', (new_hash, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── NOTIFICATIONS & SHORTCUTS ──────────────────────────────────────────────────
@app.route('/api/notifications')
@auth_required
def api_notifications():
    uid = get_current_user_id()
    conn = get_db()
    products = conn.execute('''
        SELECT p.id, p.name, p.unit, p.low_stock_threshold, p.storage_loc,
            COALESCE((SELECT SUM(quantity) FROM stock_entries WHERE product_id=p.id AND user_id=?),0) -
            COALESCE((SELECT SUM(quantity_sold) FROM sales WHERE product_id=p.id AND user_id=?),0) as available
        FROM products p
        WHERE p.user_id=?
    ''', (uid, uid, uid)).fetchall()
    conn.close()

    alerts = []
    for p in products:
        avail = p['available']
        thresh = p['low_stock_threshold'] or 0
        if avail <= 0:
            alerts.append({
                'type': 'out_of_stock',
                'severity': 'danger',
                'product_id': p['id'],
                'product_name': p['name'],
                'available': avail,
                'unit': p['unit'],
                'message': f'{p["name"]} is OUT OF STOCK (0 {p["unit"]})'
            })
        elif thresh > 0 and avail <= thresh:
            alerts.append({
                'type': 'low_stock',
                'severity': 'warning',
                'product_id': p['id'],
                'product_name': p['name'],
                'available': avail,
                'unit': p['unit'],
                'message': f'{p["name"]} is low ({avail:.2f} {p["unit"]} left &lt; {thresh:.2f})'
            })

    return jsonify({'count': len(alerts), 'alerts': alerts})


# ── DASHBOARD (WITH TIMEFRAME STATS FILTERS) ──────────────────────────────────
@app.route('/api/dashboard')
@auth_required
def api_dashboard():
    uid = get_current_user_id()
    period = request.args.get('period', 'all_time')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    s_filter, e_filter = get_date_range_filter(period, start_date, end_date)

    conn = get_db()
    c = conn.cursor()

    if s_filter and e_filter:
        total_sales = c.execute(
            'SELECT COALESCE(SUM(total_amount),0) FROM sales WHERE user_id=? AND sale_date BETWEEN ? AND ?',
            (uid, s_filter, e_filter)
        ).fetchone()[0]
        total_expenses = c.execute(
            'SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND expense_date BETWEEN ? AND ?',
            (uid, s_filter, e_filter)
        ).fetchone()[0]
        total_purchase_cost = c.execute(
            'SELECT COALESCE(SUM(total_cost),0) FROM stock_entries WHERE user_id=? AND purchase_date BETWEEN ? AND ?',
            (uid, s_filter, e_filter)
        ).fetchone()[0]
        sale_count = c.execute('''
            SELECT COUNT(DISTINCT CASE WHEN invoice_no != "" THEN invoice_no ELSE 'S-' || id END) 
            FROM sales WHERE user_id=? AND sale_date BETWEEN ? AND ?
        ''', (uid, s_filter, e_filter)).fetchone()[0]
    else:
        total_sales = c.execute('SELECT COALESCE(SUM(total_amount),0) FROM sales WHERE user_id=?', (uid,)).fetchone()[0]
        total_expenses = c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=?', (uid,)).fetchone()[0]
        total_purchase_cost = c.execute('SELECT COALESCE(SUM(total_cost),0) FROM stock_entries WHERE user_id=?', (uid,)).fetchone()[0]
        sale_count = c.execute('''
            SELECT COUNT(DISTINCT CASE WHEN invoice_no != "" THEN invoice_no ELSE 'S-' || id END) 
            FROM sales WHERE user_id=?
        ''', (uid,)).fetchone()[0]

    net_profit = total_sales - total_expenses - total_purchase_cost

    product_count = c.execute('SELECT COUNT(*) FROM products WHERE user_id=?', (uid,)).fetchone()[0]
    client_count = c.execute('SELECT COUNT(DISTINCT client_name) FROM sales WHERE user_id=?', (uid,)).fetchone()[0]

    today_str = datetime.now().strftime('%Y-%m-%d')
    today_sales = c.execute(
        'SELECT COALESCE(SUM(total_amount),0) FROM sales WHERE user_id=? AND sale_date=?', (uid, today_str)
    ).fetchone()[0]

    this_month_str = datetime.now().strftime('%Y-%m')
    month_sales = c.execute(
        'SELECT COALESCE(SUM(total_amount),0) FROM sales WHERE user_id=? AND strftime("%Y-%m",sale_date)=?', (uid, this_month_str)
    ).fetchone()[0]
    month_expenses = c.execute(
        'SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND strftime("%Y-%m",expense_date)=?', (uid, this_month_str)
    ).fetchone()[0]

    recent_sales = c.execute('''
        SELECT s.id, s.invoice_no, s.client_name, p.name as product_name, s.quantity_sold,
               s.unit_price, s.total_amount, s.sale_date, s.payment_status, p.unit, s.product_id
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=?
        ORDER BY s.created_at DESC LIMIT 8
    ''', (uid,)).fetchall()

    conn.close()
    return jsonify({
        'period': period,
        'filter_applied': bool(s_filter and e_filter),
        'start_date': s_filter,
        'end_date': e_filter,
        'total_sales': round(total_sales, 2),
        'total_expenses': round(total_expenses, 2),
        'total_purchase_cost': round(total_purchase_cost, 2),
        'net_profit': round(net_profit, 2),
        'product_count': product_count,
        'client_count': client_count,
        'sale_count': sale_count,
        'today_sales': round(today_sales, 2),
        'month_sales': round(month_sales, 2),
        'month_expenses': round(month_expenses, 2),
        'recent_sales': [dict(r) for r in recent_sales],
    })


# ── PERIOD SUMMARY & AUDIT STATEMENT REPORT ────────────────────────────────────
@app.route('/api/reports/period-summary')
@auth_required
def api_period_summary():
    uid = get_current_user_id()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        # Default to current month
        today = datetime.now().date()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    conn = get_db()
    c = conn.cursor()

    # User details
    user = c.execute('SELECT full_name, business_name, address, tax_id, phone, currency FROM users WHERE id=?', (uid,)).fetchone()

    # Sales in period
    sales = c.execute('''
        SELECT s.*, p.name as product_name, p.unit, p.category, p.sku, p.batch_no
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=? AND s.sale_date BETWEEN ? AND ?
        ORDER BY s.sale_date ASC, s.id ASC
    ''', (uid, start_date, end_date)).fetchall()

    # Purchases in period
    purchases = c.execute('''
        SELECT se.*, p.name as product_name, p.unit, p.category, p.sku
        FROM stock_entries se JOIN products p ON se.product_id=p.id
        WHERE se.user_id=? AND se.purchase_date BETWEEN ? AND ?
        ORDER BY se.purchase_date ASC, se.id ASC
    ''', (uid, start_date, end_date)).fetchall()

    # Expenses in period
    expenses = c.execute('''
        SELECT * FROM expenses
        WHERE user_id=? AND expense_date BETWEEN ? AND ?
        ORDER BY expense_date ASC, id ASC
    ''', (uid, start_date, end_date)).fetchall()

    # Aggregate calculations
    total_sales = sum(s['total_amount'] for s in sales)
    total_purchases = sum(p['total_cost'] for p in purchases)
    total_expenses = sum(e['amount'] for e in expenses)
    net_profit = total_sales - total_purchases - total_expenses
    total_units_sold = sum(s['quantity_sold'] for s in sales)
    distinct_invoices = len(set(s['invoice_no'] or f"INV-{s['id']}" for s in sales))
    distinct_clients = len(set(s['client_name'] for s in sales))

    # Product Performance in this period
    product_stats = c.execute('''
        SELECT p.name, p.unit, p.category,
               SUM(s.quantity_sold) as units_sold,
               SUM(s.total_amount) as total_revenue,
               COUNT(*) as order_count
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=? AND s.sale_date BETWEEN ? AND ?
        GROUP BY s.product_id ORDER BY total_revenue DESC
    ''', (uid, start_date, end_date)).fetchall()

    conn.close()

    return jsonify({
        'user': dict(user) if user else {},
        'period': {
            'start_date': start_date,
            'end_date': end_date,
            'generated_at': datetime.now().strftime('%d %b %Y, %I:%M %p')
        },
        'summary': {
            'total_sales': round(total_sales, 2),
            'total_purchases': round(total_purchases, 2),
            'total_expenses': round(total_expenses, 2),
            'net_profit': round(net_profit, 2),
            'total_units_sold': round(total_units_sold, 2),
            'distinct_invoices': distinct_invoices,
            'distinct_clients': distinct_clients,
            'purchases_count': len(purchases),
            'expenses_count': len(expenses)
        },
        'product_breakdown': [dict(p) for p in product_stats],
        'sales_log': [dict(s) for s in sales],
        'purchases_log': [dict(p) for p in purchases],
        'expenses_log': [dict(e) for e in expenses]
    })


@app.route('/api/reports/period-summary/pdf')
@auth_required
def api_period_summary_pdf():
    uid = get_current_user_id()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        today = datetime.now().date()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    conn = get_db()
    c = conn.cursor()
    user = c.execute('SELECT full_name, business_name, address, tax_id, phone, currency FROM users WHERE id=?', (uid,)).fetchone()

    sales = c.execute('''
        SELECT s.*, p.name as product_name, p.unit, p.category, p.sku, p.batch_no
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=? AND s.sale_date BETWEEN ? AND ?
        ORDER BY s.sale_date ASC, s.id ASC
    ''', (uid, start_date, end_date)).fetchall()

    purchases = c.execute('''
        SELECT se.*, p.name as product_name, p.unit, p.category, p.sku
        FROM stock_entries se JOIN products p ON se.product_id=p.id
        WHERE se.user_id=? AND se.purchase_date BETWEEN ? AND ?
        ORDER BY se.purchase_date ASC, se.id ASC
    ''', (uid, start_date, end_date)).fetchall()

    expenses = c.execute('''
        SELECT * FROM expenses
        WHERE user_id=? AND expense_date BETWEEN ? AND ?
        ORDER BY expense_date ASC, id ASC
    ''', (uid, start_date, end_date)).fetchall()

    total_sales = sum(s['total_amount'] for s in sales)
    total_purchases = sum(p['total_cost'] for p in purchases)
    total_expenses = sum(e['amount'] for e in expenses)
    gross_profit = total_sales - total_purchases
    net_profit = total_sales - total_purchases - total_expenses

    product_stats = c.execute('''
        SELECT p.name as product_name, p.unit, p.category,
               SUM(s.quantity_sold) as units_sold,
               SUM(s.total_amount) as revenue,
               COUNT(*) as order_count
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=? AND s.sale_date BETWEEN ? AND ?
        GROUP BY s.product_id ORDER BY revenue DESC
    ''', (uid, start_date, end_date)).fetchall()
    conn.close()

    rep_data = {
        'business_name': (user['business_name'] if user and user['business_name'] else '') or (user['full_name'] if user and user['full_name'] else '') or (user['username'] if user and user['username'] else 'Wholesale Store'),
        'currency': user['currency'] if user else 'PKR',
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': datetime.now().strftime('%d %b %Y, %I:%M %p'),
        'kpi': {
            'sales_revenue': round(total_sales, 2),
            'stock_purchases': round(total_purchases, 2),
            'gross_profit': round(gross_profit, 2),
            'operating_expenses': round(total_expenses, 2),
            'net_profit': round(net_profit, 2),
        },
        'product_breakdown': [dict(p) for p in product_stats],
        'expenses_log': [dict(e) for e in expenses]
    }

    pdf_bytes = pdf_generator.build_audit_report_pdf(rep_data)
    filename = f"Audit-Statement-{start_date}-to-{end_date}.pdf"
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# ── ANALYTICS ─────────────────────────────────────────────────────────────────
@app.route('/api/analytics')
@auth_required
def api_analytics_data():
    uid = get_current_user_id()
    conn = get_db()
    c = conn.cursor()

    monthly_sales = c.execute('''
        SELECT strftime('%Y-%m', sale_date) as month,
               strftime('%b %y', sale_date) as label,
               SUM(total_amount) as revenue,
               COUNT(DISTINCT CASE WHEN invoice_no != "" THEN invoice_no ELSE 'S-' || id END) as orders
        FROM sales WHERE user_id=? GROUP BY month ORDER BY month ASC LIMIT 12
    ''', (uid,)).fetchall()

    exp_rows = c.execute('''
        SELECT strftime('%Y-%m', expense_date) as month, SUM(amount) as expenses
        FROM expenses WHERE user_id=? GROUP BY month
    ''', (uid,)).fetchall()
    pur_rows = c.execute('''
        SELECT strftime('%Y-%m', purchase_date) as month, SUM(total_cost) as purchases
        FROM stock_entries WHERE user_id=? GROUP BY month
    ''', (uid,)).fetchall()

    exp_map = {r['month']: (r['expenses'] or 0) for r in exp_rows}
    pur_map = {r['month']: (r['purchases'] or 0) for r in pur_rows}

    monthly = []
    for row in monthly_sales:
        m = row['month']
        rev = row['revenue'] or 0
        exp = exp_map.get(m, 0)
        pur = pur_map.get(m, 0)
        profit = rev - exp - pur
        monthly.append({
            'month': m, 'label': row['label'] or m,
            'revenue': round(rev, 2), 'expenses': round(exp, 2),
            'purchases': round(pur, 2), 'profit': round(profit, 2),
            'orders': row['orders'] or 0
        })

    product_revenue = c.execute('''
        SELECT p.id, p.name, p.category, p.sku, p.unit,
               COALESCE(SUM(s.total_amount), 0) as revenue,
               COALESCE(SUM(s.quantity_sold), 0) as units, COUNT(*) as orders
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=?
        GROUP BY s.product_id ORDER BY revenue DESC LIMIT 8
    ''', (uid,)).fetchall()

    client_revenue = c.execute('''
        SELECT client_name, COALESCE(SUM(total_amount), 0) as total,
               COUNT(DISTINCT CASE WHEN invoice_no != "" THEN invoice_no ELSE 'S-' || id END) as orders,
               MAX(sale_date) as last_order
        FROM sales WHERE user_id=? GROUP BY client_name ORDER BY total DESC LIMIT 8
    ''', (uid,)).fetchall()

    category_revenue = c.execute('''
        SELECT p.category, COALESCE(SUM(s.total_amount), 0) as revenue
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=?
        GROUP BY p.category ORDER BY revenue DESC
    ''', (uid,)).fetchall()

    conn.close()
    return jsonify({
        'monthly': monthly,
        'product_revenue': [dict(r) for r in product_revenue],
        'client_revenue': [dict(r) for r in client_revenue],
        'category_revenue': [dict(r) for r in category_revenue],
    })


# ── STOCK AVAILABILITY & DETAILS ──────────────────────────────────────────────
@app.route('/api/stock/available/<int:product_id>')
@auth_required
def api_stock_available(product_id):
    uid = get_current_user_id()
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id=? AND user_id=?', (product_id, uid)).fetchone()
    if not product:
        conn.close()
        return jsonify({'available': 0, 'unit': '', 'error': 'Product not found'}), 404

    purchased = conn.execute(
        'SELECT COALESCE(SUM(quantity),0), COALESCE(SUM(total_cost),0) FROM stock_entries WHERE product_id=? AND user_id=?', (product_id, uid)
    ).fetchone()
    sold = conn.execute(
        'SELECT COALESCE(SUM(quantity_sold),0), COALESCE(SUM(total_amount),0) FROM sales WHERE product_id=? AND user_id=?', (product_id, uid)
    ).fetchone()
    conn.close()

    total_purchased = purchased[0] or 0
    total_cost = purchased[1] or 0
    total_sold = sold[0] or 0
    available = round(total_purchased - total_sold, 2)
    avg_cost = round(total_cost / total_purchased, 2) if total_purchased > 0 else 0

    return jsonify({
        'product_id': product_id,
        'available': available,
        'unit': product['unit'],
        'product_name': product['name'],
        'sku': product['sku'] or '',
        'category': product['category'],
        'batch_no': product['batch_no'] or '',
        'expiry_date': product['expiry_date'] or '',
        'storage_loc': product['storage_loc'] or '',
        'total_purchased': round(total_purchased, 2),
        'total_sold': round(total_sold, 2),
        'avg_cost_per_unit': avg_cost,
        'low_stock_threshold': product['low_stock_threshold'] or 0,
        'is_low_stock': bool(available <= (product['low_stock_threshold'] or 0) and (product['low_stock_threshold'] or 0) > 0)
    })


# ── INVOICES ───────────────────────────────────────────────────────────────────
@app.route('/api/invoices')
@auth_required
def api_invoices():
    uid = get_current_user_id()
    conn = get_db()
    c = conn.cursor()
    
    rows = c.execute('''
        SELECT 
            COALESCE(NULLIF(s.invoice_no, ''), 'INV-' || s.id) as inv_id,
            s.client_name,
            s.sale_date,
            s.payment_status,
            s.notes,
            COUNT(*) as item_count,
            ROUND(SUM(s.total_amount), 2) as grand_total,
            GROUP_CONCAT(p.name || ' (' || s.quantity_sold || ' ' || p.unit || ')', ', ') as items_summary
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.user_id = ?
        GROUP BY inv_id
        ORDER BY s.sale_date DESC, s.id DESC
    ''', (uid,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


def get_invoice_data(inv_id, uid=None):
    conn = get_db()
    c = conn.cursor()

    if uid:
        user = conn.execute('SELECT username, full_name, business_name, address, tax_id, phone, currency FROM users WHERE id=?', (uid,)).fetchone()
    else:
        # Determine user from sales record for public sharing
        sale_owner = conn.execute('SELECT user_id FROM sales WHERE invoice_no=? OR id=? LIMIT 1', (inv_id, int(inv_id[4:]) if (inv_id.startswith('INV-') and inv_id[4:].isdigit()) else -1)).fetchone()
        owner_id = sale_owner['user_id'] if sale_owner else 1
        user = conn.execute('SELECT username, full_name, business_name, address, tax_id, phone, currency, bank_details, invoice_notes FROM users WHERE id=?', (owner_id,)).fetchone()
        uid = owner_id

    biz_name = (user['business_name'] if user and user['business_name'] else '') or (user['full_name'] if user and user['full_name'] else '') or (user['username'] if user and user['username'] else 'Wholesale Store')
    biz_phone = user['phone'] if user else ''
    biz_addr = user['address'] if user else ''
    biz_tax = user['tax_id'] if user else ''
    currency = user['currency'] if user else 'PKR'

    if inv_id.startswith('INV-') and inv_id[4:].isdigit() and not inv_id.startswith('PND-INV-'):
        single_id = int(inv_id[4:])
        items = c.execute('''
            SELECT s.*, p.name as product_name, p.unit, p.sku, p.category, p.batch_no, p.expiry_date
            FROM sales s JOIN products p ON s.product_id=p.id
            WHERE s.id = ? AND s.user_id = ?
        ''', (single_id, uid)).fetchall()
    else:
        items = c.execute('''
            SELECT s.*, p.name as product_name, p.unit, p.sku, p.category, p.batch_no, p.expiry_date
            FROM sales s JOIN products p ON s.product_id=p.id
            WHERE s.invoice_no = ? AND s.user_id = ?
            ORDER BY s.id ASC
        ''', (inv_id, uid)).fetchall()

    conn.close()
    if not items:
        return None

    first = items[0]
    grand_total = sum(item['total_amount'] for item in items)
    return {
        'invoice_no': inv_id,
        'business_name': biz_name,
        'business_phone': biz_phone,
        'business_address': biz_addr,
        'tax_id': biz_tax,
        'currency': currency,
        'bank_details': (user['bank_details'] if user and 'bank_details' in user.keys() and user['bank_details'] else '') or '',
        'invoice_notes': (user['invoice_notes'] if user and 'invoice_notes' in user.keys() and user['invoice_notes'] else '') or '',
        'client_name': first['client_name'],
        'sale_date': first['sale_date'],
        'payment_status': first['payment_status'],
        'notes': first['notes'] or '',
        'grand_total': round(grand_total, 2),
        'item_count': len(items),
        'items': [dict(item) for item in items]
    }


@app.route('/api/invoice/<inv_id>')
@auth_required
def api_invoice_detail(inv_id):
    uid = get_current_user_id()
    inv = get_invoice_data(inv_id, uid)
    if not inv:
        return jsonify({'error': 'Invoice not found'}), 404
    return jsonify(inv)


@app.route('/api/invoice/<inv_id>/pdf')
@auth_required
def api_invoice_pdf(inv_id):
    uid = get_current_user_id()
    inv = get_invoice_data(inv_id, uid)
    if not inv:
        return jsonify({'error': 'Invoice not found'}), 404

    pdf_bytes = pdf_generator.build_invoice_pdf(inv)
    filename = f"{inv['invoice_no']}.pdf"
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@app.route('/invoice/<inv_id>/pdf')
def public_invoice_pdf(inv_id):
    # Direct public access for WhatsApp link recipients
    inv = get_invoice_data(inv_id, None)
    if not inv:
        return "Invoice not found or expired", 404

    pdf_bytes = pdf_generator.build_invoice_pdf(inv)
    filename = f"{inv['invoice_no']}.pdf"
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# ── CLIENT DETAIL ──────────────────────────────────────────────────────────────
@app.route('/api/client/<path:client_name>')
@auth_required
def api_client_detail(client_name):
    uid = get_current_user_id()
    conn = get_db()
    summary = conn.execute('''
        SELECT COUNT(DISTINCT CASE WHEN invoice_no != "" THEN invoice_no ELSE 'S-' || id END) as order_count,
               ROUND(SUM(total_amount),2) as total_spent,
               MAX(sale_date) as last_order,
               MIN(sale_date) as first_order
        FROM sales WHERE user_id=? AND client_name=?
    ''', (uid, client_name)).fetchone()

    sales = conn.execute('''
        SELECT s.id, s.invoice_no, s.quantity_sold, s.unit_price, s.total_amount, s.sale_date,
               s.payment_status, s.notes, p.name as product_name, p.unit
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=? AND s.client_name=? ORDER BY s.sale_date DESC, s.id DESC LIMIT 30
    ''', (uid, client_name)).fetchall()

    conn.close()
    return jsonify({
        'client_name': client_name,
        'summary': dict(summary) if summary else {},
        'sales': [dict(s) for s in sales]
    })


# ── PRODUCT STATS ──────────────────────────────────────────────────────────────
@app.route('/api/product/<int:pid>/stats')
@auth_required
def api_product_stats(pid):
    uid = get_current_user_id()
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id=? AND user_id=?', (pid, uid)).fetchone()
    if not product:
        conn.close()
        return jsonify({'error': 'Product not found'}), 404

    pur = conn.execute(
        'SELECT COALESCE(SUM(quantity),0), COALESCE(SUM(total_cost),0) FROM stock_entries WHERE product_id=? AND user_id=?', (pid, uid)
    ).fetchone()
    sol = conn.execute(
        'SELECT COALESCE(SUM(quantity_sold),0), COALESCE(SUM(total_amount),0) FROM sales WHERE product_id=? AND user_id=?', (pid, uid)
    ).fetchone()

    recent_purchases = conn.execute('''
        SELECT quantity, total_cost, supplier, purchase_date, notes
        FROM stock_entries WHERE product_id=? AND user_id=? ORDER BY purchase_date DESC, id DESC LIMIT 5
    ''', (pid, uid)).fetchall()
    recent_sales = conn.execute('''
        SELECT client_name, invoice_no, quantity_sold, unit_price, total_amount, sale_date, payment_status
        FROM sales WHERE product_id=? AND user_id=? ORDER BY sale_date DESC, id DESC LIMIT 5
    ''', (pid, uid)).fetchall()

    conn.close()
    total_purchased = round(pur[0] or 0, 2)
    total_cost = round(pur[1] or 0, 2)
    total_sold = round(sol[0] or 0, 2)
    total_revenue = round(sol[1] or 0, 2)
    current_stock = round(total_purchased - total_sold, 2)

    return jsonify({
        'product': dict(product),
        'unit': product['unit'],
        'total_purchased': total_purchased,
        'total_cost': total_cost,
        'total_sold': total_sold,
        'total_revenue': total_revenue,
        'current_stock': current_stock,
        'avg_cost_per_unit': round(total_cost / total_purchased, 2) if total_purchased > 0 else 0,
        'avg_sell_price': round(total_revenue / total_sold, 2) if total_sold > 0 else 0,
        'recent_purchases': [dict(r) for r in recent_purchases],
        'recent_sales': [dict(r) for r in recent_sales],
    })


# ── STOCK LEVELS ───────────────────────────────────────────────────────────────
@app.route('/api/stock/levels')
@auth_required
def api_stock_levels():
    uid = get_current_user_id()
    conn = get_db()
    rows = conn.execute('''
        SELECT p.id, p.name, p.unit, p.category, p.sku, p.batch_no, p.expiry_date, p.storage_loc, p.low_stock_threshold,
            COALESCE((SELECT SUM(quantity) FROM stock_entries WHERE product_id=p.id AND user_id=?),0) as total_purchased,
            COALESCE((SELECT SUM(total_cost) FROM stock_entries WHERE product_id=p.id AND user_id=?),0) as total_invested,
            COALESCE((SELECT SUM(quantity_sold) FROM sales WHERE product_id=p.id AND user_id=?),0) as total_sold,
            COALESCE((SELECT SUM(total_amount) FROM sales WHERE product_id=p.id AND user_id=?),0) as total_revenue
        FROM products p WHERE p.user_id=? ORDER BY p.name ASC
    ''', (uid, uid, uid, uid, uid)).fetchall()
    result = []
    for row in rows:
        r = dict(row)
        r['current_stock'] = round(r['total_purchased'] - r['total_sold'], 2)
        r['avg_cost_per_unit'] = round(r['total_invested'] / r['total_purchased'], 2) if r['total_purchased'] > 0 else 0
        r['avg_sell_price'] = round(r['total_revenue'] / r['total_sold'], 2) if r['total_sold'] > 0 else 0
        r['stock_value'] = round(r['current_stock'] * r['avg_cost_per_unit'], 2)
        r['is_low_stock'] = bool(r['current_stock'] <= (r['low_stock_threshold'] or 0) and (r['low_stock_threshold'] or 0) > 0)
        result.append(r)
    conn.close()
    return jsonify(result)


# ── PRODUCTS ───────────────────────────────────────────────────────────────────
@app.route('/api/products', methods=['GET'])
@auth_required
def api_get_products():
    uid = get_current_user_id()
    conn = get_db()
    products = conn.execute('''
        SELECT p.*,
            COALESCE((SELECT SUM(quantity) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id), 0) -
            COALESCE((SELECT SUM(quantity_sold) FROM sales WHERE product_id=p.id AND user_id=p.user_id), 0) as current_stock,
            COALESCE((SELECT SUM(quantity_sold) FROM sales WHERE product_id=p.id AND user_id=p.user_id), 0) as total_sold,
            COALESCE((SELECT SUM(total_amount) FROM sales WHERE product_id=p.id AND user_id=p.user_id), 0) as total_revenue,
            COALESCE((SELECT COUNT(*) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id), 0) as restock_count,
            COALESCE((SELECT MAX(purchase_date) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id), '') as last_restocked,
            COALESCE((SELECT SUM(total_cost)/NULLIF(SUM(quantity),0) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id), 0) as avg_cost,
            COALESCE((SELECT SUM(total_amount)/NULLIF(SUM(quantity_sold),0) FROM sales WHERE product_id=p.id AND user_id=p.user_id), 0) as avg_price
        FROM products p
        WHERE p.user_id=?
        ORDER BY p.name ASC
    ''', (uid,)).fetchall()
    conn.close()
    return jsonify([dict(p) for p in products])


@app.route('/api/products', methods=['POST'])
@auth_required
def api_add_product():
    uid = get_current_user_id()
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    sku = data.get('sku', '').strip()
    category = data.get('category', '').strip()
    unit = data.get('unit', '').strip()
    batch_no = data.get('batch_no', '').strip()
    expiry_date = data.get('expiry_date', '').strip()
    storage_loc = data.get('storage_loc', '').strip()
    brand = data.get('brand', '').strip()
    description = data.get('description', '').strip()
    min_order_qty = float(data.get('min_order_qty', 0) or 0)
    threshold = float(data.get('low_stock_threshold', 0) or 0)

    if not name or not category or not unit:
        return jsonify({'error': 'Name, category, and unit are required'}), 400

    conn = get_db()
    try:
        conn.execute(
            '''INSERT INTO products (user_id,name,sku,category,unit,batch_no,expiry_date,storage_loc,brand,description,min_order_qty,low_stock_threshold)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (uid, name, sku, category, unit, batch_no, expiry_date, storage_loc, brand, description, min_order_qty, threshold)
        )
        conn.commit()
        pid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()
        return jsonify({'success': True, 'id': pid}), 201
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/<int:pid>', methods=['PUT'])
@auth_required
def api_edit_product(pid):
    uid = get_current_user_id()
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    category = data.get('category', '').strip()
    unit = data.get('unit', '').strip()
    if not name or not category or not unit:
        return jsonify({'error': 'Name, category, and unit are required'}), 400

    conn = get_db()
    conn.execute('''UPDATE products SET name=?,sku=?,category=?,unit=?,batch_no=?,expiry_date=?,storage_loc=?,brand=?,description=?,
                    min_order_qty=?,low_stock_threshold=? WHERE id=? AND user_id=?''',
                 (name, data.get('sku', '').strip(), category, unit,
                  data.get('batch_no', '').strip(), data.get('expiry_date', '').strip(),
                  data.get('storage_loc', '').strip(), data.get('brand', '').strip(),
                  data.get('description', '').strip(), float(data.get('min_order_qty', 0) or 0),
                  float(data.get('low_stock_threshold', 0) or 0), pid, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/products/<int:pid>', methods=['DELETE'])
@auth_required
def api_delete_product(pid):
    uid = get_current_user_id()
    conn = get_db()
    sc = conn.execute('SELECT COUNT(*) FROM sales WHERE product_id=? AND user_id=?', (pid, uid)).fetchone()[0]
    stc = conn.execute('SELECT COUNT(*) FROM stock_entries WHERE product_id=? AND user_id=?', (pid, uid)).fetchone()[0]
    if sc > 0 or stc > 0:
        conn.close()
        return jsonify({'error': 'Cannot delete: product has linked stock or sales records'}), 400
    conn.execute('DELETE FROM products WHERE id=? AND user_id=?', (pid, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── STOCK ENTRIES ──────────────────────────────────────────────────────────────
@app.route('/api/stock', methods=['GET'])
@auth_required
def api_get_stock():
    uid = get_current_user_id()
    conn = get_db()
    entries = conn.execute('''
        SELECT se.*, p.name as product_name, p.unit, p.category, p.sku, p.batch_no, p.storage_loc
        FROM stock_entries se JOIN products p ON se.product_id=p.id
        WHERE se.user_id=?
        ORDER BY se.purchase_date DESC, se.created_at DESC
    ''', (uid,)).fetchall()
    conn.close()
    return jsonify([dict(e) for e in entries])


@app.route('/api/stock', methods=['POST'])
@auth_required
def api_add_stock():
    uid = get_current_user_id()
    data = request.get_json() or {}
    product_id = data.get('product_id')
    quantity = data.get('quantity')
    total_cost = data.get('total_cost')
    supplier = data.get('supplier', '').strip()
    purchase_date = data.get('purchase_date', datetime.now().strftime('%Y-%m-%d'))
    notes = data.get('notes', '').strip()

    if not product_id or not quantity or total_cost is None:
        return jsonify({'error': 'Product, quantity, and cost are required'}), 400
    try:
        quantity = float(quantity)
        total_cost = float(total_cost)
        if quantity <= 0 or total_cost < 0:
            raise ValueError()
    except Exception:
        return jsonify({'error': 'Quantity must be positive; cost must be non-negative'}), 400

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO stock_entries (user_id,product_id,quantity,total_cost,supplier,purchase_date,notes) VALUES (?,?,?,?,?,?,?)',
            (uid, product_id, quantity, total_cost, supplier, purchase_date, notes)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True}), 201
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stock/<int:sid>', methods=['PUT'])
@auth_required
def api_edit_stock(sid):
    uid = get_current_user_id()
    data = request.get_json() or {}
    try:
        quantity = float(data.get('quantity', 0))
        total_cost = float(data.get('total_cost', 0))
        if quantity <= 0 or total_cost < 0:
            raise ValueError()
    except Exception:
        return jsonify({'error': 'Invalid quantity or cost'}), 400

    conn = get_db()
    conn.execute(
        'UPDATE stock_entries SET product_id=?,quantity=?,total_cost=?,supplier=?,purchase_date=?,notes=? WHERE id=? AND user_id=?',
        (data.get('product_id'), quantity, total_cost, data.get('supplier', '').strip(),
         data.get('purchase_date'), data.get('notes', '').strip(), sid, uid)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/stock/<int:sid>', methods=['DELETE'])
@auth_required
def api_delete_stock(sid):
    uid = get_current_user_id()
    conn = get_db()
    conn.execute('DELETE FROM stock_entries WHERE id=? AND user_id=?', (sid, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── SALES & ORDERS ─────────────────────────────────────────────────────────────
@app.route('/api/sales', methods=['GET'])
@auth_required
def api_get_sales():
    uid = get_current_user_id()
    conn = get_db()
    sales = conn.execute('''
        SELECT s.*, p.name as product_name, p.unit, p.category, p.sku
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=?
        ORDER BY s.sale_date DESC, s.created_at DESC
    ''', (uid,)).fetchall()
    conn.close()
    return jsonify([dict(s) for s in sales])


@app.route('/api/sales', methods=['POST'])
@auth_required
def api_add_sale():
    uid = get_current_user_id()
    data = request.get_json() or {}
    client_name = data.get('client_name', '').strip()
    sale_date = data.get('sale_date', datetime.now().strftime('%Y-%m-%d'))
    payment_status = data.get('payment_status', 'Paid')
    notes = data.get('notes', '').strip()

    if not client_name:
        return jsonify({'error': 'Client name is required'}), 400

    items = data.get('items')
    if not items:
        product_id = data.get('product_id')
        qty = data.get('quantity_sold')
        amt = data.get('total_amount')
        unit_price = data.get('unit_price', 0)
        if not product_id or not qty or amt is None:
            return jsonify({'error': 'Product, quantity and amount are required'}), 400
        items = [{'product_id': product_id, 'quantity_sold': qty, 'total_amount': amt, 'unit_price': unit_price}]

    if not isinstance(items, list) or len(items) == 0:
        return jsonify({'error': 'At least one product item is required for sale'}), 400

    conn = get_db()
    c = conn.cursor()

    try:
        req_by_product = {}
        for idx, item in enumerate(items):
            pid = item.get('product_id')
            if not pid:
                conn.close()
                return jsonify({'error': f'Item #{idx+1} is missing product selection'}), 400
            try:
                q = float(item.get('quantity_sold', 0))
                a = float(item.get('total_amount', 0))
                if q <= 0 or a < 0:
                    raise ValueError()
            except Exception:
                conn.close()
                return jsonify({'error': f'Item #{idx+1} has invalid quantity or amount'}), 400
            req_by_product[int(pid)] = req_by_product.get(int(pid), 0) + q

        # Stock Validation
        for pid, requested_qty in req_by_product.items():
            product = c.execute('SELECT name, unit FROM products WHERE id=? AND user_id=?', (pid, uid)).fetchone()
            if not product:
                conn.close()
                return jsonify({'error': f'Product ID {pid} not found in inventory'}), 404

            total_purchased = c.execute(
                'SELECT COALESCE(SUM(quantity),0) FROM stock_entries WHERE product_id=? AND user_id=?', (pid, uid)
            ).fetchone()[0]
            total_sold_prev = c.execute(
                'SELECT COALESCE(SUM(quantity_sold),0) FROM sales WHERE product_id=? AND user_id=?', (pid, uid)
            ).fetchone()[0]
            available = round(total_purchased - total_sold_prev, 2)

            if requested_qty > available:
                conn.close()
                return jsonify({
                    'error': f'Insufficient stock for "{product["name"]}". Only {available} {product["unit"]} available in stock, but requested {requested_qty} {product["unit"]}.',
                    'available': available,
                    'unit': product['unit'],
                    'product_name': product['name'],
                    'product_id': pid
                }), 400

        # Generate unique Invoice Number
        invoice_no = generate_invoice_no(c, uid)

        for item in items:
            pid = int(item['product_id'])
            q = float(item['quantity_sold'])
            a = float(item['total_amount'])
            u_price = float(item.get('unit_price') or (a / q if q > 0 else 0))
            c.execute(
                '''INSERT INTO sales (user_id, invoice_no, client_name, product_id, quantity_sold, unit_price, total_amount, sale_date, payment_status, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (uid, invoice_no, client_name, pid, q, u_price, a, sale_date, payment_status, notes)
            )

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'invoice_no': invoice_no, 'items_count': len(items)}), 201
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/sales/<int:sid>', methods=['PUT'])
@auth_required
def api_edit_sale(sid):
    uid = get_current_user_id()
    data = request.get_json() or {}
    client_name = data.get('client_name', '').strip()
    product_id = data.get('product_id')
    try:
        quantity_sold = float(data.get('quantity_sold', 0))
        total_amount = float(data.get('total_amount', 0))
        unit_price = float(data.get('unit_price') or (total_amount / quantity_sold if quantity_sold > 0 else 0))
        if quantity_sold <= 0 or total_amount < 0:
            raise ValueError()
    except Exception:
        return jsonify({'error': 'Invalid values'}), 400

    conn = get_db()
    current = conn.execute('SELECT quantity_sold, product_id FROM sales WHERE id=? AND user_id=?', (sid, uid)).fetchone()
    if not current:
        conn.close()
        return jsonify({'error': 'Sale record not found'}), 404

    old_qty = current['quantity_sold']
    old_pid = current['product_id']
    check_pid = int(product_id) if product_id else old_pid

    total_purchased = conn.execute(
        'SELECT COALESCE(SUM(quantity),0) FROM stock_entries WHERE product_id=? AND user_id=?', (check_pid, uid)
    ).fetchone()[0]
    total_sold_all = conn.execute(
        'SELECT COALESCE(SUM(quantity_sold),0) FROM sales WHERE product_id=? AND user_id=?', (check_pid, uid)
    ).fetchone()[0]

    available = total_purchased - total_sold_all + (old_qty if check_pid == old_pid else 0)

    if quantity_sold > available:
        unit = conn.execute('SELECT unit FROM products WHERE id=? AND user_id=?', (check_pid, uid)).fetchone()['unit']
        conn.close()
        return jsonify({
            'error': f'Insufficient stock. Only {available:.2f} {unit} available.',
            'available': round(available, 2),
            'unit': unit
        }), 400

    conn.execute(
        '''UPDATE sales SET client_name=?,product_id=?,quantity_sold=?,unit_price=?,total_amount=?,sale_date=?,payment_status=?,notes=?
           WHERE id=? AND user_id=?''',
        (client_name, check_pid, quantity_sold, unit_price, total_amount,
         data.get('sale_date'), data.get('payment_status', 'Paid'), data.get('notes', '').strip(), sid, uid)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/sales/<int:sid>', methods=['DELETE'])
@auth_required
def api_delete_sale(sid):
    uid = get_current_user_id()
    conn = get_db()
    conn.execute('DELETE FROM sales WHERE id=? AND user_id=?', (sid, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── CLIENTS ────────────────────────────────────────────────────────────────────
@app.route('/api/clients')
@auth_required
def api_clients():
    uid = get_current_user_id()
    conn = get_db()
    clients = conn.execute('''
        SELECT client_name,
               COUNT(DISTINCT CASE WHEN invoice_no != "" THEN invoice_no ELSE 'S-' || id END) as order_count,
               ROUND(SUM(total_amount),2) as total_spent,
               MAX(sale_date) as last_order,
               COUNT(DISTINCT product_id) as product_variety
        FROM sales WHERE user_id=? GROUP BY client_name ORDER BY total_spent DESC
    ''', (uid,)).fetchall()
    conn.close()
    return jsonify([dict(c) for c in clients])


# ── EXPENSES ───────────────────────────────────────────────────────────────────
@app.route('/api/expenses', methods=['GET'])
@auth_required
def api_get_expenses():
    uid = get_current_user_id()
    conn = get_db()
    expenses = conn.execute(
        'SELECT * FROM expenses WHERE user_id=? ORDER BY expense_date DESC, created_at DESC', (uid,)
    ).fetchall()
    conn.close()
    return jsonify([dict(e) for e in expenses])


@app.route('/api/expenses', methods=['POST'])
@auth_required
def api_add_expense():
    uid = get_current_user_id()
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    amount = data.get('amount')
    expense_date = data.get('expense_date', datetime.now().strftime('%Y-%m-%d'))
    category = data.get('category', '').strip()
    payment_method = data.get('payment_method', 'Cash')
    notes = data.get('notes', '').strip()

    if not title or not amount:
        return jsonify({'error': 'Title and amount are required'}), 400
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError()
    except Exception:
        return jsonify({'error': 'Amount must be positive'}), 400

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO expenses (user_id,title,amount,expense_date,category,payment_method,notes) VALUES (?,?,?,?,?,?,?)',
            (uid, title, amount, expense_date, category, payment_method, notes)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True}), 201
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/expenses/<int:eid>', methods=['PUT'])
@auth_required
def api_edit_expense(eid):
    uid = get_current_user_id()
    data = request.get_json() or {}
    try:
        amount = float(data.get('amount', 0))
        if amount <= 0:
            raise ValueError()
    except Exception:
        return jsonify({'error': 'Invalid amount'}), 400

    conn = get_db()
    conn.execute(
        'UPDATE expenses SET title=?,amount=?,expense_date=?,category=?,payment_method=?,notes=? WHERE id=? AND user_id=?',
        (data.get('title', '').strip(), amount, data.get('expense_date'),
         data.get('category', '').strip(), data.get('payment_method', 'Cash'), data.get('notes', '').strip(), eid, uid)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/expenses/<int:eid>', methods=['DELETE'])
@auth_required
def api_delete_expense(eid):
    uid = get_current_user_id()
    conn = get_db()
    conn.execute('DELETE FROM expenses WHERE id=? AND user_id=?', (eid, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── ANALYSIS ───────────────────────────────────────────────────────────────────
@app.route('/api/analysis')
@auth_required
def api_analysis():
    uid = get_current_user_id()
    conn = get_db()
    total_purchase_cost = conn.execute('SELECT COALESCE(SUM(total_cost),0) FROM stock_entries WHERE user_id=?', (uid,)).fetchone()[0]

    sales_data = conn.execute('''
        SELECT s.product_id, p.name, p.category, p.unit, p.sku,
               SUM(s.quantity_sold) as total_sold,
               SUM(s.total_amount) as total_revenue,
               COUNT(*) as order_count
        FROM sales s JOIN products p ON s.product_id=p.id
        WHERE s.user_id=?
        GROUP BY s.product_id
    ''', (uid,)).fetchall()

    total_units_sold_all = sum(r['total_sold'] for r in sales_data) or 1

    result = []
    for row in sales_data:
        total_sold = row['total_sold']
        revenue = row['total_revenue']
        proportion = total_sold / total_units_sold_all
        estimated_cost = round(proportion * total_purchase_cost, 2)
        net_profit = round(revenue - estimated_cost, 2)
        result.append({
            'product_id': row['product_id'],
            'product_name': row['name'],
            'category': row['category'],
            'unit': row['unit'],
            'sku': row['sku'] or '',
            'total_units_sold': round(total_sold, 2),
            'order_count': row['order_count'],
            'total_revenue': round(revenue, 2),
            'estimated_cost': estimated_cost,
            'net_profit': net_profit,
            'margin_percent': round((net_profit / revenue * 100) if revenue > 0 else 0, 1),
            'avg_sell_price': round(revenue / total_sold, 2) if total_sold > 0 else 0,
            'avg_cost_per_unit': round(estimated_cost / total_sold, 2) if total_sold > 0 else 0,
        })

    result.sort(key=lambda x: x['total_revenue'], reverse=True)
    conn.close()
    return jsonify({'products': result, 'total_purchase_cost': round(total_purchase_cost, 2)})


# ── DATABASE BACKUP FOR OWNER ──────────────────────────────────────────────────
@app.route('/api/admin/backup-db')
@auth_required
def api_backup_db():
    if os.path.exists(DB_PATH):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(DB_PATH, as_attachment=True, download_name=f'pandas_erp_backup_{ts}.db')
    return jsonify({'error': 'Database file not found'}), 404


# Always initialize DB schema on import/run
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


@app.route('/api/analytics/business-intelligence')
@auth_required
def api_business_intelligence():
    uid = get_current_user_id()
    conn = get_db()
    c = conn.cursor()

    user = c.execute('SELECT currency FROM users WHERE id=?', (uid,)).fetchone()
    currency = user['currency'] if user and user['currency'] else 'PKR'

    prods = c.execute('''
        SELECT p.*,
            COALESCE((SELECT SUM(quantity) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id), 0) -
            COALESCE((SELECT SUM(quantity_sold) FROM sales WHERE product_id=p.id AND user_id=p.user_id), 0) as current_stock,
            COALESCE((SELECT SUM(quantity_sold) FROM sales WHERE product_id=p.id AND user_id=p.user_id), 0) as total_sold,
            COALESCE((SELECT SUM(total_amount) FROM sales WHERE product_id=p.id AND user_id=p.user_id), 0) as total_revenue,
            COALESCE((SELECT COUNT(*) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id), 0) as restock_count,
            COALESCE((SELECT MAX(purchase_date) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id), '') as last_restocked,
            COALESCE((SELECT MAX(sale_date) FROM sales WHERE product_id=p.id AND user_id=p.user_id), '') as last_sold_date,
            COALESCE((SELECT SUM(total_cost)/NULLIF(SUM(quantity),0) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id), 0) as avg_cost,
            COALESCE((SELECT SUM(total_amount)/NULLIF(SUM(quantity_sold),0) FROM sales WHERE product_id=p.id AND user_id=p.user_id), 0) as avg_price
        FROM products p
        WHERE p.user_id=?
        ORDER BY p.name ASC
    ''', (uid,)).fetchall()

    product_list = [dict(p) for p in prods]
    capital_tied_up = sum(max(0, p['current_stock']) * (p['avg_cost'] or 0) for p in product_list)
    total_store_revenue = sum(p['total_revenue'] or 0 for p in product_list)
    total_store_sold_units = sum(p['total_sold'] or 0 for p in product_list)

    slow_moving = []
    fast_moving = []
    reorder_alerts = []
    margin_stars = []

    today = date.today()

    for p in product_list:
        stock = p['current_stock']
        sold = p['total_sold']
        cost = p['avg_cost'] or 0
        price = p['avg_price'] or 0
        threshold = p.get('low_stock_threshold') or 5
        margin_pct = round(((price - cost) / price * 100), 1) if price > cost and price > 0 else 0
        p['margin_pct'] = margin_pct
        p['tied_capital'] = round(max(0, stock) * cost, 2)

        if stock <= threshold:
            reorder_alerts.append({
                **p,
                'advice': f"Critical shortage: only {stock:g} {p['unit']} left (Threshold: {threshold:g}). Replenish stock immediately to avoid lost sales."
            })

        if sold > 0:
            share = round((p['total_revenue'] / total_store_revenue * 100), 1) if total_store_revenue > 0 else 0
            p['revenue_share_pct'] = share
            fast_moving.append(p)

        days_since_sold = 999
        if p['last_sold_date']:
            try:
                days_since_sold = (today - date.fromisoformat(p['last_sold_date'])).days
            except Exception:
                pass

        if stock > 0 and (sold == 0 or days_since_sold >= 14):
            slow_moving.append({
                **p,
                'days_inactive': days_since_sold if sold > 0 else 'Never sold',
                'advice': f"Capital of {currency} {p['tied_capital']:,.2f} is idle. Run a 5-10% bundle discount or flash deal to unlock working capital."
            })

        if margin_pct >= 20:
            margin_stars.append({
                **p,
                'advice': f"Exceptional profit margin of {margin_pct}%. Train staff to highlight and prioritize this SKU on checkout bills."
            })

    fast_moving.sort(key=lambda x: x['total_sold'], reverse=True)
    margin_stars.sort(key=lambda x: x['margin_pct'], reverse=True)
    slow_moving.sort(key=lambda x: x['tied_capital'], reverse=True)

    clients = c.execute('''
        SELECT client_name, COUNT(*) as order_count, SUM(total_amount) as total_spent, 
               MAX(sale_date) as last_order_date, AVG(total_amount) as avg_order_val
        FROM sales
        WHERE user_id=?
        GROUP BY client_name
        ORDER BY total_spent DESC
        LIMIT 6
    ''', (uid,)).fetchall()
    vip_clients = [dict(cli) for cli in clients]
    for cli in vip_clients:
        cli['advice'] = f"Top-tier client with {cli['order_count']} lifetime orders ({currency} {cli['total_spent']:,.2f}). Provide VIP support and payment flexibility."

    executive_advice = []
    if reorder_alerts:
        names = ", ".join([x['name'] for x in reorder_alerts[:2]])
        executive_advice.append({
            'type': 'warning',
            'title': 'Supply Chain & Stockout Alert',
            'desc': f"{len(reorder_alerts)} item(s) are running critically low ({names}). Create replenishment purchase orders right away.",
            'action_tab': 'stock',
            'action_label': 'Open Stock Purchases'
        })

    if slow_moving:
        total_slow_cap = sum(x['tied_capital'] for x in slow_moving)
        executive_advice.append({
            'type': 'info',
            'title': 'Working Capital Liquidity Optimization',
            'desc': f"{currency} {total_slow_cap:,.2f} is currently locked in slow-moving inventory. Consider special bundle deals or wholesale clearance offers.",
            'action_tab': 'sales',
            'action_label': 'Create Promotional Sale'
        })

    if fast_moving:
        top_prod = fast_moving[0]
        executive_advice.append({
            'type': 'success',
            'title': 'Core Revenue Driver Protection',
            'desc': f"'{top_prod['name']}' is your #1 best seller ({top_prod['total_sold']:g} units sold). Keep a reliable 2-week supplier buffer to prevent stockouts.",
            'action_tab': 'products',
            'action_label': 'View Product Directory'
        })

    if margin_stars:
        top_margin = margin_stars[0]
        executive_advice.append({
            'type': 'profit',
            'title': 'High Margin Profit Focus',
            'desc': f"'{top_margin['name']}' generates an outstanding {top_margin['margin_pct']}% margin. Upsell this SKU prominently during checkout.",
            'action_tab': 'sales',
            'action_label': 'Add to Invoice'
        })

    if not executive_advice:
        executive_advice.append({
            'type': 'info',
            'title': 'Catalog Operations In Optimal Balance',
            'desc': 'Sales velocity and inventory levels are aligned. Continue recording daily commercial transactions for deeper trends.',
            'action_tab': 'dashboard',
            'action_label': 'Go to Dashboard'
        })

    conn.close()

    return jsonify({
        'summary': {
            'currency': currency,
            'capital_tied_up': round(capital_tied_up, 2),
            'total_store_revenue': round(total_store_revenue, 2),
            'total_sold_units': round(total_store_sold_units, 2),
            'active_reorder_count': len(reorder_alerts),
            'slow_moving_count': len(slow_moving),
            'total_products': len(product_list)
        },
        'executive_advice': executive_advice,
        'reorder_alerts': reorder_alerts,
        'slow_moving': slow_moving,
        'fast_moving': fast_moving[:8],
        'margin_stars': margin_stars[:8],
        'vip_clients': vip_clients
    })


@app.route('/api/user/export-backup', methods=['POST'])
@auth_required
def api_user_export_backup():
    uid = get_current_user_id()
    data = request.get_json() or {}
    password = data.get('password', '').strip()

    if not password:
        return jsonify({'error': 'Account password is required to authorize data backup.'}), 400

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    if not user or not check_password_hash(user['password_hash'], password):
        conn.close()
        return jsonify({'error': 'Incorrect password. Data backup authorization rejected.'}), 403

    user_dict = dict(user)
    user_dict.pop('password_hash', None)

    products = [dict(r) for r in conn.execute('''
        SELECT p.*,
            COALESCE((SELECT SUM(quantity) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id),0) -
            COALESCE((SELECT SUM(quantity_sold) FROM sales WHERE product_id=p.id AND user_id=p.user_id),0) as available,
            COALESCE(
                NULLIF(p.purchase_price, 0),
                (SELECT total_cost / quantity FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id AND quantity>0 ORDER BY purchase_date DESC, id DESC LIMIT 1),
                (SELECT SUM(total_cost) / NULLIF(SUM(quantity), 0) FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id),
                0.0
            ) as effective_cost,
            COALESCE(
                NULLIF(p.selling_price, 0),
                (SELECT unit_price FROM sales WHERE product_id=p.id AND user_id=p.user_id AND unit_price>0 ORDER BY sale_date DESC, id DESC LIMIT 1),
                (SELECT total_amount / NULLIF(quantity_sold, 0) FROM sales WHERE product_id=p.id AND user_id=p.user_id AND quantity_sold>0 ORDER BY sale_date DESC, id DESC LIMIT 1),
                0.0
            ) as effective_sale_price,
            COALESCE(
                (SELECT purchase_date FROM stock_entries WHERE product_id=p.id AND user_id=p.user_id ORDER BY purchase_date DESC, id DESC LIMIT 1),
                SUBSTR(p.created_at, 1, 10)
            ) as last_action_date
        FROM products p
        WHERE p.user_id=?
        ORDER BY p.name ASC
    ''', (uid,)).fetchall()]

    stock_entries = [dict(r) for r in conn.execute('''
        SELECT s.*, p.name as product_name, p.unit
        FROM stock_entries s
        LEFT JOIN products p ON s.product_id=p.id
        WHERE s.user_id=?
        ORDER BY s.purchase_date DESC, s.id DESC
    ''', (uid,)).fetchall()]

    sales = [dict(r) for r in conn.execute('''
        SELECT sl.*, p.name as product_name, p.unit
        FROM sales sl
        LEFT JOIN products p ON sl.product_id=p.id
        WHERE sl.user_id=?
        ORDER BY sl.sale_date DESC, sl.id DESC
    ''', (uid,)).fetchall()]

    expenses = [dict(r) for r in conn.execute('''
        SELECT * FROM expenses
        WHERE user_id=?
        ORDER BY expense_date DESC, id DESC
    ''', (uid,)).fetchall()]
    conn.close()

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, 'static', 'logo.jpg')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(base_dir, 'static', 'icon-512.png')

        pdf_bytes = pdf_generator.build_user_backup_pdf(user_dict, products, stock_entries, sales, expenses, logo_path=logo_path)
        safe_username = "".join(c for c in user_dict.get('username', 'user') if c.isalnum() or c in ('_', '-'))
        filename = f"PANDA_Store_Statement_{safe_username}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': f'Failed to generate PDF backup statement: {str(e)}'}), 500
