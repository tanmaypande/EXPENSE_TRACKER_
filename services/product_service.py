from models.database import get_db_connection

def get_products(business_id, search=None, category_id=None, low_stock=False, limit=100):
    conn = get_db_connection()
    query = """
    SELECT p.*, c.name as category_name
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.id
    WHERE p.business_id = ? AND p.is_active = 1
    """
    params = [business_id]

    if search:
        s = f"%{search.strip().lower()}%"
        query += " AND (LOWER(p.name) LIKE ? OR LOWER(p.sku) LIKE ? OR LOWER(p.barcode) LIKE ? OR LOWER(p.brand) LIKE ?)"
        params.extend([s, s, s, s])

    if category_id:
        query += " AND p.category_id = ?"
        params.append(category_id)

    if low_stock:
        query += " AND p.stock_quantity <= p.min_stock_level"

    query += " ORDER BY p.name ASC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_product_by_id(product_id, business_id=None):
    conn = get_db_connection()
    if business_id:
        row = conn.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ? AND p.business_id = ?
        """, (product_id, business_id)).fetchone()
    else:
        row = conn.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
        """, (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def find_product_by_barcode_or_sku(business_id, code):
    if not code:
        return None
    c = code.strip()
    conn = get_db_connection()
    row = conn.execute("""
    SELECT p.*, c.name as category_name
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.id
    WHERE p.business_id = ? AND p.is_active = 1 AND (p.barcode = ? OR p.sku = ?)
    LIMIT 1
    """, (business_id, c, c)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_product(business_id, name, sku=None, barcode=None, category_id=None, brand=None, 
                   purchase_price=0.0, selling_price=0.0, tax_rate=0.0, stock_quantity=0.0, 
                   min_stock_level=5.0, unit="pcs", description=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO products
    (business_id, name, sku, barcode, category_id, brand, purchase_price, selling_price, tax_rate, stock_quantity, min_stock_level, unit, description)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        business_id, name.strip(), (sku or "").strip(), (barcode or "").strip(), category_id,
        (brand or "").strip(), float(purchase_price or 0.0), float(selling_price or 0.0),
        float(tax_rate or 0.0), float(stock_quantity or 0.0), float(min_stock_level or 5.0),
        unit or "pcs", description
    ))
    conn.commit()
    prod_id = cur.lastrowid

    # Record initial stock movement if quantity > 0
    if float(stock_quantity or 0.0) > 0:
        cur.execute("""
        INSERT INTO stock_movements (business_id, product_id, change_qty, new_stock, reason, notes)
        VALUES (?, ?, ?, ?, 'initial', 'Product added to inventory')
        """, (business_id, prod_id, float(stock_quantity), float(stock_quantity)))
        conn.commit()

    conn.close()
    return prod_id

def update_product(product_id, business_id, name, sku, barcode, category_id, brand,
                   purchase_price, selling_price, tax_rate, min_stock_level, unit, description):
    conn = get_db_connection()
    conn.execute("""
    UPDATE products
    SET name = ?, sku = ?, barcode = ?, category_id = ?, brand = ?,
        purchase_price = ?, selling_price = ?, tax_rate = ?, min_stock_level = ?, unit = ?, description = ?
    WHERE id = ? AND business_id = ?
    """, (
        name.strip(), (sku or "").strip(), (barcode or "").strip(), category_id,
        (brand or "").strip(), float(purchase_price or 0.0), float(selling_price or 0.0),
        float(tax_rate or 0.0), float(min_stock_level or 5.0), unit or "pcs", description,
        product_id, business_id
    ))
    conn.commit()
    conn.close()

def adjust_stock(business_id, product_id, adjustment_qty, reason="adjustment", notes=""):
    """Atomically modifies stock quantity with audit logging."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT stock_quantity FROM products WHERE id = ? AND business_id = ?", (product_id, business_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError("Product not found")

    old_stock = row["stock_quantity"]
    new_stock = max(0.0, old_stock + float(adjustment_qty))

    cur.execute("UPDATE products SET stock_quantity = ? WHERE id = ? AND business_id = ?", (new_stock, product_id, business_id))
    cur.execute("""
    INSERT INTO stock_movements (business_id, product_id, change_qty, new_stock, reason, notes)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (business_id, product_id, float(adjustment_qty), new_stock, reason, notes))

    conn.commit()
    conn.close()
    return new_stock

def get_stock_movements(business_id, product_id=None, limit=50):
    conn = get_db_connection()
    query = """
    SELECT sm.*, p.name as product_name, p.sku, p.unit
    FROM stock_movements sm
    JOIN products p ON sm.product_id = p.id
    WHERE sm.business_id = ?
    """
    params = [business_id]
    if product_id:
        query += " AND sm.product_id = ?"
        params.append(product_id)

    query += " ORDER BY sm.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_categories(business_id):
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT c.*, COUNT(p.id) as product_count
    FROM categories c
    LEFT JOIN products p ON c.id = p.category_id AND p.is_active = 1
    WHERE c.business_id = ?
    GROUP BY c.id
    ORDER BY c.name ASC
    """, (business_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_category(business_id, name, description=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO categories (business_id, name, description) VALUES (?, ?, ?)", (business_id, name.strip(), description))
    conn.commit()
    cat_id = cur.lastrowid
    conn.close()
    return cat_id
