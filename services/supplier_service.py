from models.database import get_db_connection

def get_suppliers(business_id, search=None, status_filter=None, limit=100):
    conn = get_db_connection()
    query = """
    SELECT s.*,
           (SELECT COUNT(*) FROM purchases WHERE supplier_id = s.id) as total_purchases_count
    FROM suppliers s
    WHERE s.business_id = ?
    """
    params = [business_id]

    if search:
        term = f"%{search.strip().lower()}%"
        query += " AND (LOWER(s.name) LIKE ? OR LOWER(s.contact_person) LIKE ? OR LOWER(s.phone) LIKE ? OR LOWER(s.email) LIKE ? OR LOWER(s.gstin) LIKE ?)"
        params.extend([term, term, term, term, term])

    if status_filter == "due":
        query += " AND s.outstanding_balance > 0"
    elif status_filter == "clear":
        query += " AND (s.outstanding_balance = 0 OR s.outstanding_balance IS NULL)"

    query += " ORDER BY s.name ASC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_supplier_by_id(supplier_id, business_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM suppliers WHERE id = ? AND business_id = ?", (supplier_id, business_id)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_supplier(business_id, supplier_id, name, contact_person="", phone="", email="", address="", gstin=""):
    name = (name or "").strip()
    if not name:
        raise ValueError("Supplier name cannot be empty.")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE suppliers
    SET name = ?, contact_person = ?, phone = ?, email = ?, address = ?, gstin = ?
    WHERE id = ? AND business_id = ?
    """, (name, contact_person.strip(), phone.strip(), email.strip(), address.strip(), gstin.strip().upper(), supplier_id, business_id))
    conn.commit()
    conn.close()
    return True

def delete_supplier(business_id, supplier_id):
    conn = get_db_connection()
    cur = conn.cursor()
    # Unlink purchases to preserve inward stock and accounting records
    cur.execute("UPDATE purchases SET supplier_id = NULL WHERE supplier_id = ? AND business_id = ?", (supplier_id, business_id))
    cur.execute("DELETE FROM suppliers WHERE id = ? AND business_id = ?", (supplier_id, business_id))
    conn.commit()
    conn.close()
    return True

def get_supplier_details(supplier_id, business_id):
    conn = get_db_connection()
    supplier = conn.execute("SELECT * FROM suppliers WHERE id = ? AND business_id = ?", (supplier_id, business_id)).fetchone()
    if not supplier:
        conn.close()
        return None

    purchases = conn.execute("""
    SELECT p.*,
           ROUND(p.total_amount - p.paid_amount, 2) as balance_amount,
           (SELECT COUNT(*) FROM purchase_items WHERE purchase_id = p.id) as item_count
    FROM purchases p
    WHERE p.supplier_id = ? AND p.business_id = ?
    ORDER BY p.created_at DESC
    """, (supplier_id, business_id)).fetchall()

    conn.close()
    p_list = [dict(p) for p in purchases]
    total_inward_value = sum(p["total_amount"] for p in p_list)
    total_paid_value = sum(p["paid_amount"] for p in p_list)
    total_due_value = sum(p["balance_amount"] for p in p_list)

    return {
        "supplier": dict(supplier),
        "purchases": p_list,
        "total_inward_value": round(total_inward_value, 2),
        "total_paid_value": round(total_paid_value, 2),
        "total_due_value": round(total_due_value, 2),
        "total_po_count": len(p_list)
    }

def create_supplier(business_id, name, contact_person="", phone="", email="", address="", gstin=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO suppliers (business_id, name, contact_person, phone, email, address, gstin)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (business_id, name.strip(), contact_person.strip(), phone.strip(), email.strip(), address.strip(), gstin.strip().upper()))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid

def create_purchase(business_id, supplier_id, purchase_number, items, paid_amount=0.0, payment_method="cash", notes=""):
    """
    Records a purchase order from a vendor:
    1. Inserts into purchases & purchase_items
    2. Automatically increments product stock
    3. Logs stock movement 'purchase'
    4. Updates supplier balance if credit
    """
    if not items:
        raise ValueError("Cannot create purchase with zero items.")

    total_amount = sum(float(i["quantity"]) * float(i["purchase_price"]) for i in items)
    paid = float(paid_amount or 0.0)
    unpaid_balance = max(0.0, round(total_amount - paid, 2))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        sup_name = "Direct Vendor"
        if supplier_id:
            s_row = cur.execute("SELECT name FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
            if s_row: sup_name = s_row["name"]

        cur.execute("""
        INSERT INTO purchases 
        (business_id, purchase_number, supplier_id, supplier_name, total_amount, paid_amount, payment_method, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (business_id, purchase_number.strip(), supplier_id, sup_name, total_amount, paid, payment_method, notes))
        purchase_id = cur.lastrowid

        for itm in items:
            pid = itm["product_id"]
            qty = float(itm["quantity"])
            cost = float(itm["purchase_price"])
            item_total = round(qty * cost, 2)

            cur.execute("""
            INSERT INTO purchase_items (purchase_id, product_id, product_name, quantity, purchase_price, total_amount)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (purchase_id, pid, itm.get("product_name", "Stock Item"), qty, cost, item_total))

            # Increment stock and update purchase price in catalog
            p_row = cur.execute("SELECT stock_quantity FROM products WHERE id = ?", (pid,)).fetchone()
            current_stock = p_row["stock_quantity"] if p_row else 0.0
            new_stock = current_stock + qty

            cur.execute("""
            UPDATE products 
            SET stock_quantity = ?, purchase_price = ?
            WHERE id = ? AND business_id = ?
            """, (new_stock, cost, pid, business_id))

            # Audit movement
            cur.execute("""
            INSERT INTO stock_movements (business_id, product_id, change_qty, new_stock, reason, reference_id, notes)
            VALUES (?, ?, ?, ?, 'purchase', ?, ?)
            """, (business_id, pid, qty, new_stock, purchase_number, f"Inward stock via {purchase_number}"))

        # Update supplier totals
        if supplier_id:
            cur.execute("""
            UPDATE suppliers 
            SET total_purchases = total_purchases + ?,
                outstanding_balance = outstanding_balance + ?
            WHERE id = ? AND business_id = ?
            """, (total_amount, unpaid_balance, supplier_id, business_id))

        conn.commit()
        return purchase_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_purchases(business_id, limit=50):
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT p.*,
           ROUND(p.total_amount - p.paid_amount, 2) as balance_amount,
           s.name as supplier_name,
           s.phone as supplier_phone,
           (SELECT COUNT(*) FROM purchase_items WHERE purchase_id = p.id) as item_count
    FROM purchases p
    LEFT JOIN suppliers s ON p.supplier_id = s.id
    WHERE p.business_id = ?
    ORDER BY p.created_at DESC
    LIMIT ?
    """, (business_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
