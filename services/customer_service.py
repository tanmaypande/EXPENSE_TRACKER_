from models.database import get_db_connection

def get_customers(business_id, search=None, status_filter=None, sort_by=None, limit=100):
    conn = get_db_connection()
    query = """
    SELECT c.*, 
           (SELECT COUNT(*) FROM sales WHERE customer_id = c.id) as total_invoices
    FROM customers c
    WHERE c.business_id = ?
    """
    params = [business_id]

    if search:
        s = f"%{search.strip().lower()}%"
        query += " AND (LOWER(c.name) LIKE ? OR LOWER(c.phone) LIKE ? OR LOWER(c.email) LIKE ? OR LOWER(c.gstin) LIKE ?)"
        params.extend([s, s, s, s])

    if status_filter == "due":
        query += " AND c.outstanding_balance > 0"
    elif status_filter == "clear":
        query += " AND (c.outstanding_balance = 0 OR c.outstanding_balance IS NULL)"

    if sort_by == "balance_desc":
        query += " ORDER BY c.outstanding_balance DESC, c.name ASC"
    elif sort_by == "name_desc":
        query += " ORDER BY c.name DESC"
    elif sort_by == "newest":
        query += " ORDER BY c.created_at DESC"
    elif sort_by == "spent_desc":
        query += " ORDER BY c.total_spent DESC"
    else:
        query += " ORDER BY c.name ASC"

    query += " LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_customer(business_id, customer_id, name, phone=None, email=None, address=None, gstin=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Customer name cannot be empty.")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE customers
    SET name = ?, phone = ?, email = ?, address = ?, gstin = ?
    WHERE id = ? AND business_id = ?
    """, (name, (phone or "").strip(), (email or "").strip(), (address or "").strip(), (gstin or "").strip().upper(), customer_id, business_id))
    conn.commit()
    conn.close()
    return True

def delete_customer(business_id, customer_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        c_row = cur.execute("SELECT name, outstanding_balance FROM customers WHERE id = ? AND business_id = ?", (customer_id, business_id)).fetchone()
        if not c_row:
            return False
        if float(c_row["outstanding_balance"] or 0.0) > 0:
            raise ValueError(f"Cannot delete customer '{c_row['name']}' with active outstanding Udhar balance of ₹{c_row['outstanding_balance']:.2f}. Settle all balances first.")
        # Unlink any associated sales so invoices remain historically accurate
        cur.execute("UPDATE sales SET customer_id = NULL WHERE customer_id = ? AND business_id = ?", (customer_id, business_id))
        cur.execute("DELETE FROM customer_payments WHERE customer_id = ? AND business_id = ?", (customer_id, business_id))
        cur.execute("DELETE FROM customers WHERE id = ? AND business_id = ?", (customer_id, business_id))
        conn.commit()
        return True
    finally:
        conn.close()

def get_customer_by_id(customer_id, business_id):
    conn = get_db_connection()
    row = conn.execute("""
    SELECT * FROM customers WHERE id = ? AND business_id = ?
    """, (customer_id, business_id)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_or_get_customer(business_id, name, phone=None, email=None, address=None, gstin=None):
    name = (name or "Walk-in Customer").strip()
    phone = (phone or "").strip()
    conn = get_db_connection()
    cur = conn.cursor()

    # If phone is provided, check if customer exists
    if phone:
        existing = cur.execute("SELECT * FROM customers WHERE business_id = ? AND phone = ?", (business_id, phone)).fetchone()
        if existing:
            conn.close()
            return dict(existing)

    cur.execute("""
    INSERT INTO customers (business_id, name, phone, email, address, gstin)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (business_id, name, phone, (email or "").strip(), (address or "").strip(), (gstin or "").strip()))
    conn.commit()
    cid = cur.lastrowid
    new_c = cur.execute("SELECT * FROM customers WHERE id = ?", (cid,)).fetchone()
    conn.close()
    return dict(new_c)

def get_customer_ledger(customer_id, business_id):
    conn = get_db_connection()
    customer = conn.execute("SELECT * FROM customers WHERE id = ? AND business_id = ?", (customer_id, business_id)).fetchone()
    if not customer:
        conn.close()
        return None

    # Invoices for customer
    invoices = conn.execute("""
    SELECT id, invoice_number, grand_total, paid_amount, balance_amount, payment_method, payment_status, created_at
    FROM sales
    WHERE customer_id = ? AND business_id = ?
    ORDER BY created_at DESC
    """, (customer_id, business_id)).fetchall()

    # Payments made by customer to settle credit
    payments = conn.execute("""
    SELECT id, amount, payment_method, notes, created_at
    FROM customer_payments
    WHERE customer_id = ? AND business_id = ?
    ORDER BY created_at DESC
    """, (customer_id, business_id)).fetchall()

    conn.close()
    return {
        "customer": dict(customer),
        "invoices": [dict(i) for i in invoices],
        "payments": [dict(p) for p in payments]
    }

def record_customer_payment(business_id, customer_id, amount, payment_method="cash", notes=""):
    amt = float(amount or 0.0)
    if amt <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO customer_payments (business_id, customer_id, amount, payment_method, notes)
        VALUES (?, ?, ?, ?, ?)
        """, (business_id, customer_id, amt, payment_method, notes))

        # Decrement outstanding balance
        cur.execute("""
        UPDATE customers
        SET outstanding_balance = MAX(0.0, outstanding_balance - ?)
        WHERE id = ? AND business_id = ?
        """, (amt, customer_id, business_id))

        conn.commit()
    finally:
        conn.close()
