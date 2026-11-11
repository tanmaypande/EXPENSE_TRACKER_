from models.database import get_db_connection

def search_sale_for_return(business_id, invoice_number):
    conn = get_db_connection()
    sale = conn.execute("""
    SELECT * FROM sales WHERE invoice_number = ? AND business_id = ?
    """, (invoice_number.strip(), business_id)).fetchone()

    if not sale:
        conn.close()
        return None

    items = conn.execute("""
    SELECT si.*,
           COALESCE((
               SELECT SUM(ri.quantity)
               FROM return_items ri
               JOIN returns r ON ri.return_id = r.id
               WHERE r.sale_id = si.sale_id AND ri.product_id = si.product_id
           ), 0.0) as already_returned_qty
    FROM sale_items si
    WHERE si.sale_id = ?
    """, (sale["id"],)).fetchall()

    conn.close()
    return {
        "sale": dict(sale),
        "items": [dict(i) for i in items]
    }

def process_return(business_id, sale_id, return_items_data, refund_method="cash", reason=""):
    """
    Executes a sales return:
    1. Strictly validates: return_qty <= (sold_qty - already_returned_qty)
    2. Calculates refund amount
    3. If restock=1, increments product stock and logs stock movement
    4. Records return & return_items
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        sale = cur.execute("SELECT * FROM sales WHERE id = ? AND business_id = ?", (sale_id, business_id)).fetchone()
        if not sale:
            raise ValueError("Original invoice not found.")

        total_refund = 0.0
        validated_items = []

        for itm in return_items_data:
            pid = itm.get("product_id")
            ret_qty = float(itm.get("quantity", 0.0))
            if ret_qty <= 0:
                continue

            # Check original sale item
            s_item = cur.execute("""
            SELECT si.*,
                   COALESCE((
                       SELECT SUM(ri.quantity)
                       FROM return_items ri
                       JOIN returns r ON ri.return_id = r.id
                       WHERE r.sale_id = si.sale_id AND ri.product_id = si.product_id
                   ), 0.0) as already_returned_qty
            FROM sale_items si
            WHERE si.sale_id = ? AND (si.product_id = ? OR si.product_name = ?)
            """, (sale_id, pid, itm.get("product_name"))).fetchone()

            if not s_item:
                continue

            max_allowed = s_item["quantity"] - s_item["already_returned_qty"]
            if ret_qty > max_allowed:
                raise ValueError(f"Cannot return {ret_qty} units of '{s_item['product_name']}'. Maximum returnable quantity is {max_allowed}.")

            unit_refund = (s_item["total_amount"] / s_item["quantity"])
            item_refund = round(unit_refund * ret_qty, 2)
            total_refund += item_refund

            validated_items.append({
                "product_id": pid,
                "product_name": s_item["product_name"],
                "quantity": ret_qty,
                "unit_refund": round(unit_refund, 2),
                "total_refund": item_refund,
                "restock": 1 if itm.get("restock", True) else 0
            })

        if not validated_items:
            raise ValueError("No valid items to return.")

        # Insert into returns
        cur.execute("""
        INSERT INTO returns (business_id, sale_id, invoice_number, refund_amount, refund_method, reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (business_id, sale_id, sale["invoice_number"], round(total_refund, 2), refund_method, reason))
        return_id = cur.lastrowid

        # Insert return items & restock if selected
        for vi in validated_items:
            cur.execute("""
            INSERT INTO return_items (return_id, product_id, product_name, quantity, refund_unit_price, total_refund, restock)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (return_id, vi["product_id"], vi["product_name"], vi["quantity"], vi["unit_refund"], vi["total_refund"], vi["restock"]))

            if vi["restock"] and vi["product_id"]:
                p_row = cur.execute("SELECT stock_quantity FROM products WHERE id = ?", (vi["product_id"],)).fetchone()
                if p_row:
                    new_stock = p_row["stock_quantity"] + vi["quantity"]
                    cur.execute("UPDATE products SET stock_quantity = ? WHERE id = ?", (new_stock, vi["product_id"]))
                    cur.execute("""
                    INSERT INTO stock_movements (business_id, product_id, change_qty, new_stock, reason, reference_id, notes)
                    VALUES (?, ?, ?, ?, 'return', ?, ?)
                    """, (business_id, vi["product_id"], vi["quantity"], new_stock, sale["invoice_number"], f"Customer return on {sale['invoice_number']}"))

        # If store credit / Khata adjustment selected, reduce invoice balance & customer outstanding balance
        if refund_method.lower() in ("credit", "store_credit", "khata", "balance_adjust"):
            refund_amt = round(total_refund, 2)
            orig_balance = float(sale["balance_amount"] or 0.0)
            balance_reduction = min(orig_balance, refund_amt)
            if balance_reduction > 0:
                new_balance = max(0.0, round(orig_balance - balance_reduction, 2))
                new_status = "paid" if new_balance == 0.0 else ("partial" if float(sale["paid_amount"] or 0.0) > 0 else "unpaid")
                cur.execute("""
                UPDATE sales 
                SET balance_amount = ?, payment_status = ? 
                WHERE id = ? AND business_id = ?
                """, (new_balance, new_status, sale_id, business_id))

            if sale["customer_id"]:
                cur.execute("""
                UPDATE customers 
                SET outstanding_balance = MAX(0.0, round(outstanding_balance - ?, 2))
                WHERE id = ? AND business_id = ?
                """, (refund_amt, sale["customer_id"], business_id))

        conn.commit()
        return return_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_returns(business_id, limit=50):
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT r.*,
           (SELECT COUNT(*) FROM return_items WHERE return_id = r.id) as item_count
    FROM returns r
    WHERE r.business_id = ?
    ORDER BY r.created_at DESC
    LIMIT ?
    """, (business_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
