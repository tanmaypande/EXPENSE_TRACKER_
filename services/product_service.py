import datetime
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

def get_product_by_id(product_id, business_id=None, active_only=False):
    conn = get_db_connection()
    query = """
    SELECT p.*, c.name as category_name
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.id
    WHERE p.id = ?
    """
    params = [product_id]
    if business_id:
        query += " AND p.business_id = ?"
        params.append(business_id)
    if active_only:
        query += " AND p.is_active = 1"

    row = conn.execute(query, params).fetchone()
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

def _sanitize_category_id(category_id, conn=None):
    """Ensures category_id is either a valid existing category ID or None to prevent foreign key errors."""
    if not category_id or str(category_id).strip() in ("", "0", "None"):
        return None
    try:
        val = int(category_id)
        if val <= 0:
            return None
        if conn:
            exists = conn.execute("SELECT 1 FROM categories WHERE id = ?", (val,)).fetchone()
            if not exists:
                return None
        return val
    except (ValueError, TypeError):
        return None

def create_product(business_id, name, sku=None, barcode=None, category_id=None, brand=None, 
                   purchase_price=0.0, selling_price=0.0, tax_rate=0.0, stock_quantity=0.0, 
                   min_stock_level=5.0, unit="pcs", description=None):
    conn = get_db_connection()
    try:
        valid_cat_id = _sanitize_category_id(category_id, conn)
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO products
        (business_id, name, sku, barcode, category_id, brand, purchase_price, selling_price, tax_rate, stock_quantity, min_stock_level, unit, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            business_id, name.strip(), (sku or "").strip(), (barcode or "").strip(), valid_cat_id,
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

        return prod_id
    finally:
        conn.close()

def update_product(product_id, business_id, name, sku, barcode, category_id, brand,
                   purchase_price, selling_price, tax_rate, min_stock_level, unit, description):
    conn = get_db_connection()
    try:
        valid_cat_id = _sanitize_category_id(category_id, conn)
        conn.execute("""
        UPDATE products
        SET name = ?, sku = ?, barcode = ?, category_id = ?, brand = ?,
            purchase_price = ?, selling_price = ?, tax_rate = ?, min_stock_level = ?, unit = ?, description = ?
        WHERE id = ? AND business_id = ?
        """, (
            name.strip(), (sku or "").strip(), (barcode or "").strip(), valid_cat_id,
            (brand or "").strip(), float(purchase_price or 0.0), float(selling_price or 0.0),
            float(tax_rate or 0.0), float(min_stock_level or 5.0), unit or "pcs", description,
            product_id, business_id
        ))
        conn.commit()
    finally:
        conn.close()

def adjust_stock(business_id, product_id, adjustment_qty, reason="adjustment", notes=""):
    """Atomically modifies stock quantity with audit logging."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT stock_quantity FROM products WHERE id = ? AND business_id = ?", (product_id, business_id))
        row = cur.fetchone()
        if not row:
            raise ValueError("Product not found")

        old_stock = row["stock_quantity"]
        new_stock = max(0.0, old_stock + float(adjustment_qty))

        cur.execute("UPDATE products SET stock_quantity = ? WHERE id = ? AND business_id = ?", (new_stock, product_id, business_id))
        cur.execute("""
        INSERT INTO stock_movements (business_id, product_id, change_qty, new_stock, reason, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (business_id, product_id, float(adjustment_qty), new_stock, reason, notes))

        conn.commit()
        return new_stock
    finally:
        conn.close()

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

    query += " ORDER BY sm.created_at DESC, sm.id DESC LIMIT ?"
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

def delete_product(business_id, product_id):
    """
    Safely deletes or archives a product:
    1. Verifies ownership and existence within business_id.
    2. Checks references in transactions:
       - sale_items (invoices)
       - purchase_items (supplier purchases)
       - return_items (customer refunds)
       - stock_movements (audit trail where reason != 'initial')
    3. If referenced:
       - Soft-deletes: sets is_active = 0, deleted_at = CURRENT_TIMESTAMP, stock_quantity = 0.
       - Preserves complete historical accuracy for past invoices and accounting reports.
    4. If unreferenced (unused product):
       - Permanently removes the product and any initial setup stock movement.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        prod = cur.execute("""
        SELECT id, name, sku, stock_quantity, purchase_price, selling_price 
        FROM products 
        WHERE id = ? AND business_id = ?
        """, (product_id, business_id)).fetchone()

        if not prod:
            raise ValueError(f"Product #{product_id} not found or unauthorized.")

        # Check for historical references
        sales_cnt = cur.execute("SELECT COUNT(*) FROM sale_items WHERE product_id = ?", (product_id,)).fetchone()[0]
        purchases_cnt = cur.execute("SELECT COUNT(*) FROM purchase_items WHERE product_id = ?", (product_id,)).fetchone()[0]
        returns_cnt = cur.execute("SELECT COUNT(*) FROM return_items WHERE product_id = ?", (product_id,)).fetchone()[0]
        movements_cnt = cur.execute("SELECT COUNT(*) FROM stock_movements WHERE product_id = ? AND reason != 'initial'", (product_id,)).fetchone()[0]

        has_history = (sales_cnt > 0 or purchases_cnt > 0 or returns_cnt > 0 or movements_cnt > 0)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if has_history:
            # Soft delete / Archive: Keep historical records intact, hide from active catalog & POS
            cur.execute("""
            UPDATE products 
            SET is_active = 0, deleted_at = ?, stock_quantity = 0 
            WHERE id = ? AND business_id = ?
            """, (now_str, product_id, business_id))
            action = "archived"
            message = f"Product '{prod['name']}' has transaction history and was safely archived to preserve financial records."
        else:
            # Safe permanent deletion: No historical ties
            cur.execute("DELETE FROM stock_movements WHERE product_id = ? AND business_id = ?", (product_id, business_id))
            cur.execute("DELETE FROM products WHERE id = ? AND business_id = ?", (product_id, business_id))
            action = "deleted"
            message = f"Product '{prod['name']}' was permanently deleted from inventory."

        conn.commit()
        return {
            "success": True,
            "action": action,
            "product_id": product_id,
            "product_name": prod["name"],
            "message": message
        }
    finally:
        conn.close()
