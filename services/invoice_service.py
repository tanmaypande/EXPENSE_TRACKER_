from models.database import get_db_connection

def get_invoice_details(business_id, sale_id):
    conn = get_db_connection()
    sale = conn.execute("""
    SELECT s.*, b.name as business_name, b.phone as business_phone, b.email as business_email,
           b.address as business_address, b.gstin as business_gstin, b.currency, b.terms_conditions,
           b.tax_enabled, u.name as cashier_name
    FROM sales s
    JOIN businesses b ON s.business_id = b.id
    LEFT JOIN users u ON s.created_by = u.id
    WHERE (s.id = ? OR s.invoice_number = ?) AND s.business_id = ?
    """, (sale_id, str(sale_id), business_id)).fetchone()

    if not sale:
        conn.close()
        return None

    items = conn.execute("""
    SELECT si.*, p.unit, p.barcode
    FROM sale_items si
    LEFT JOIN products p ON si.product_id = p.id
    WHERE si.sale_id = ?
    ORDER BY si.id ASC
    """, (sale["id"],)).fetchall()

    conn.close()
    return {
        "sale": dict(sale),
        "items": [dict(i) for i in items]
    }

def get_recent_invoices(business_id, limit=50, search=None):
    conn = get_db_connection()
    query = """
    SELECT s.*, 
           (SELECT COUNT(*) FROM sale_items WHERE sale_id = s.id) as item_count
    FROM sales s
    WHERE s.business_id = ?
    """
    params = [business_id]

    if search:
        s = f"%{search.strip().lower()}%"
        query += " AND (LOWER(s.invoice_number) LIKE ? OR LOWER(s.customer_name) LIKE ? OR LOWER(s.customer_phone) LIKE ?)"
        params.extend([s, s, s])

    query += " ORDER BY s.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
