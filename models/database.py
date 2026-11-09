import os
import sys
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "expense.db")

def get_db_connection():
    """Returns a thread-safe connection to the SQLite database with row factory and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initializes and migrates the normalized ShopLedger schema while preserving existing data."""
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. USERS TABLE (Preserved & extended)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT,
        role TEXT DEFAULT 'owner',
        business_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. BUSINESSES TABLE (Shop profiles)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'retail',
        phone TEXT,
        email TEXT,
        address TEXT,
        gstin TEXT,
        currency TEXT DEFAULT '₹',
        invoice_prefix TEXT DEFAULT 'INV-',
        tax_enabled INTEGER DEFAULT 1,
        default_tax_rate REAL DEFAULT 0.0,
        terms_conditions TEXT DEFAULT 'Thank you for your business! Goods once sold cannot be returned without bill.',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 3. CATEGORIES TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
    )
    """)

    # 4. PRODUCTS TABLE (Inventory)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        sku TEXT,
        barcode TEXT,
        category_id INTEGER,
        brand TEXT,
        purchase_price REAL NOT NULL DEFAULT 0.0,
        selling_price REAL NOT NULL DEFAULT 0.0,
        tax_rate REAL DEFAULT 0.0,
        stock_quantity REAL DEFAULT 0.0,
        min_stock_level REAL DEFAULT 5.0,
        unit TEXT DEFAULT 'pcs',
        description TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
    )
    """)

    # 5. STOCK MOVEMENTS TABLE (Audit Trail)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        change_qty REAL NOT NULL,
        new_stock REAL NOT NULL,
        reason TEXT NOT NULL,
        reference_id TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )
    """)

    # 6. CUSTOMERS TABLE (CRM)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        gstin TEXT,
        total_spent REAL DEFAULT 0.0,
        outstanding_balance REAL DEFAULT 0.0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
    )
    """)

    # 7. SUPPLIERS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        gstin TEXT,
        total_purchases REAL DEFAULT 0.0,
        outstanding_balance REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
    )
    """)

    # 8. SALES / INVOICES TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        invoice_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER,
        customer_name TEXT,
        customer_phone TEXT,
        subtotal REAL NOT NULL DEFAULT 0.0,
        discount_amount REAL DEFAULT 0.0,
        tax_amount REAL DEFAULT 0.0,
        cgst_amount REAL DEFAULT 0.0,
        sgst_amount REAL DEFAULT 0.0,
        grand_total REAL NOT NULL,
        paid_amount REAL NOT NULL,
        balance_amount REAL DEFAULT 0.0,
        payment_method TEXT DEFAULT 'cash',
        payment_status TEXT DEFAULT 'paid',
        notes TEXT,
        status TEXT DEFAULT 'completed',
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )
    """)

    # 9. SALE ITEMS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT NOT NULL,
        sku TEXT,
        unit_price REAL NOT NULL,
        purchase_price REAL DEFAULT 0.0,
        quantity REAL NOT NULL,
        discount_amount REAL DEFAULT 0.0,
        tax_rate REAL DEFAULT 0.0,
        tax_amount REAL DEFAULT 0.0,
        total_amount REAL NOT NULL,
        FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    )
    """)

    # 10. PURCHASES TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        purchase_number TEXT NOT NULL,
        supplier_id INTEGER,
        supplier_name TEXT,
        total_amount REAL NOT NULL,
        paid_amount REAL DEFAULT 0.0,
        payment_method TEXT DEFAULT 'cash',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
    )
    """)

    # 11. PURCHASE ITEMS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchase_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity REAL NOT NULL,
        purchase_price REAL NOT NULL,
        total_amount REAL NOT NULL,
        FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )
    """)

    # 12. RETURNS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        sale_id INTEGER NOT NULL,
        invoice_number TEXT NOT NULL,
        refund_amount REAL NOT NULL,
        refund_method TEXT DEFAULT 'cash',
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
        FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
    )
    """)

    # 13. RETURN ITEMS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS return_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        return_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT,
        quantity REAL NOT NULL,
        refund_unit_price REAL NOT NULL,
        total_refund REAL NOT NULL,
        restock INTEGER DEFAULT 1,
        FOREIGN KEY (return_id) REFERENCES returns(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    )
    """)

    # 14. EXPENSES TABLE (Commercial Business Expenses)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        date TEXT NOT NULL,
        description TEXT,
        payment_method TEXT DEFAULT 'cash',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
    )
    """)

    # 15. CUSTOMER PAYMENTS TABLE (Credit Settlement & Installments)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customer_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        invoice_id INTEGER,
        amount REAL NOT NULL,
        payment_method TEXT DEFAULT 'cash',
        transaction_reference TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (invoice_id) REFERENCES sales(id) ON DELETE SET NULL
    )
    """)

    # 16. IN-APP NOTIFICATIONS & UDHAR REMINDERS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        customer_id INTEGER,
        invoice_id INTEGER,
        notification_type TEXT DEFAULT 'udhar_reminder',
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        amount REAL DEFAULT 0.0,
        reminder_date TEXT,
        status TEXT DEFAULT 'unread',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (invoice_id) REFERENCES sales(id) ON DELETE CASCADE
    )
    """)

    # 17. REMINDER HISTORY TABLE (5-Day cycle deduplication)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reminder_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        invoice_id INTEGER NOT NULL,
        reminder_cycle INTEGER NOT NULL,
        reminder_date TEXT NOT NULL,
        notification_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(business_id, invoice_id, reminder_cycle),
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
        FOREIGN KEY (invoice_id) REFERENCES sales(id) ON DELETE CASCADE
    )
    """)

    # 18. LEGACY RECORD TABLE PRESERVATION
    cur.execute("""
    CREATE TABLE IF NOT EXISTS record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        type TEXT DEFAULT 'expense',
        business_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # 19. SUBSCRIPTIONS TABLE (Super Admin Plan Management)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        plan TEXT DEFAULT 'trial',
        start_date TEXT NOT NULL,
        expiry_date TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
    )
    """)

    # 20. AUDIT LOGS TABLE (Platform Governance & Accountability)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        admin_email TEXT,
        action TEXT NOT NULL,
        target_user_id INTEGER,
        business_id INTEGER,
        details TEXT,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 21. PASSWORD RESETS TABLE (Single-use Secure Tokens)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # Ensure backward-compatible columns exist on sales
    cur.execute("PRAGMA table_info(sales)")
    sales_cols = [r["name"] for r in cur.fetchall()]
    if "discount_type" not in sales_cols:
        try: cur.execute("ALTER TABLE sales ADD COLUMN discount_type TEXT DEFAULT 'fixed'")
        except Exception: pass
    if "discount_value" not in sales_cols:
        try: cur.execute("ALTER TABLE sales ADD COLUMN discount_value REAL DEFAULT 0.0")
        except Exception: pass

    # Ensure backward-compatible columns exist on products
    cur.execute("PRAGMA table_info(products)")
    prod_cols = [r["name"] for r in cur.fetchall()]
    if "deleted_at" not in prod_cols:
        try: cur.execute("ALTER TABLE products ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL")
        except Exception: pass

    # Ensure backward-compatible columns exist on customer_payments
    cur.execute("PRAGMA table_info(customer_payments)")
    cp_cols = [r["name"] for r in cur.fetchall()]
    if "invoice_id" not in cp_cols:
        try: cur.execute("ALTER TABLE customer_payments ADD COLUMN invoice_id INTEGER")
        except Exception: pass
    if "transaction_reference" not in cp_cols:
        try: cur.execute("ALTER TABLE customer_payments ADD COLUMN transaction_reference TEXT")
        except Exception: pass

    # Ensure backward-compatible columns exist on users and record
    cur.execute("PRAGMA table_info(users)")
    user_cols = [r["name"] for r in cur.fetchall()]
    if "name" not in user_cols:
        try: cur.execute("ALTER TABLE users ADD COLUMN name TEXT")
        except Exception: pass
    if "role" not in user_cols:
        try: cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'owner'")
        except Exception: pass
    if "business_id" not in user_cols:
        try: cur.execute("ALTER TABLE users ADD COLUMN business_id INTEGER")
        except Exception: pass
    if "account_status" not in user_cols:
        try: cur.execute("ALTER TABLE users ADD COLUMN account_status TEXT DEFAULT 'active'")
        except Exception: pass
    if "must_change_password" not in user_cols:
        try: cur.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
        except Exception: pass
    if "session_version" not in user_cols:
        try: cur.execute("ALTER TABLE users ADD COLUMN session_version INTEGER DEFAULT 1")
        except Exception: pass
    if "phone" not in user_cols:
        try: cur.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        except Exception: pass
    if "created_at" not in user_cols:
        try: cur.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except Exception: pass

    # Ensure backward-compatible columns exist on businesses
    cur.execute("PRAGMA table_info(businesses)")
    biz_cols = [r["name"] for r in cur.fetchall()]
    if "status" not in biz_cols:
        try: cur.execute("ALTER TABLE businesses ADD COLUMN status TEXT DEFAULT 'active'")
        except Exception: pass

    cur.execute("PRAGMA table_info(record)")
    rec_cols = [r["name"] for r in cur.fetchall()]
    if "business_id" not in rec_cols:
        try: cur.execute("ALTER TABLE record ADD COLUMN business_id INTEGER")
        except Exception: pass

    # Provision Single Master Super Admin User if none exists
    admin_row = cur.execute("SELECT id FROM users WHERE role = 'SUPER_ADMIN'").fetchone()
    if not admin_row:
        import os
        from werkzeug.security import generate_password_hash
        admin_email = os.environ.get("SUPER_ADMIN_EMAIL", "tanmaypandey0604@gmail.com").strip().lower()
        admin_pass = os.environ.get("SUPER_ADMIN_PASSWORD", "TanmayAdmin@2026!")
        hashed_pass = generate_password_hash(admin_pass)
        
        # Check if email is already taken by ordinary user
        existing_user = cur.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
        if existing_user:
            cur.execute("UPDATE users SET role = 'SUPER_ADMIN', account_status = 'active', name = 'Tanmay Pandey' WHERE id = ?", (existing_user["id"],))
        else:
            cur.execute("""
            INSERT INTO users (email, password, name, role, account_status, session_version)
            VALUES (?, ?, 'Tanmay Pandey', 'SUPER_ADMIN', 'active', 1)
            """, (admin_email, hashed_pass))

    # Create helpful indexes for performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_business ON products(business_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_business ON sales(business_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice ON sales(invoice_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_expenses_business ON expenses(business_id)")

    conn.commit()
    conn.close()
    print("[DB] ShopLedger commercial database initialized successfully.")

if __name__ == "__main__":
    init_db()
