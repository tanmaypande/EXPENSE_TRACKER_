import datetime
from models.database import get_db_connection

def generate_next_invoice_number(business_id, prefix="INV-"):
    """Generates an incremental and collision-free invoice number."""
    conn = get_db_connection()
    today_str = datetime.date.today().strftime("%y%m%d")
    clean_prefix = prefix.strip() if prefix else "INV-"
    if not clean_prefix.endswith("-"):
        clean_prefix += "-"
    base_prefix = f"{clean_prefix}{today_str}-"
    
    row = conn.execute("SELECT COUNT(*) FROM sales WHERE invoice_number LIKE ?", (f"{base_prefix}%",)).fetchone()
    count = (row[0] if row else 0) + 1

    while True:
        candidate = f"{base_prefix}{count:04d}"
        exists = conn.execute("SELECT 1 FROM sales WHERE invoice_number = ?", (candidate,)).fetchone()
        if not exists:
            conn.close()
            return candidate
        count += 1

def calculate_cart_totals(items, discount_type="fixed", discount_value=0.0, discount_amount=None, tax_enabled=True):
    """
    Computes precise decimal totals for POS cart items.
    Supports both Fixed (₹) and Percentage (%) discounts.
    Calculation:
      - Subtotal = sum(item quantity * price)
      - Discount Amount = Subtotal * (Discount % / 100) or Fixed Discount (₹)
      - Taxable Amount = Subtotal - Discount Amount
      - Final Amount = Taxable Amount + Applicable Taxes
    """
    subtotal = 0.0
    raw_item_tax = 0.0
    processed_items = []

    for item in items:
        qty = float(item.get("quantity", 1.0))
        if qty <= 0:
            continue
        price = float(item.get("unit_price", 0.0))
        item_disc = float(item.get("discount", 0.0))
        item_tax_rate = float(item.get("tax_rate", 0.0)) if tax_enabled else 0.0

        item_subtotal = round(qty * price, 2)
        taxable_item = max(0.0, round(item_subtotal - item_disc, 2))
        item_tax = round(taxable_item * (item_tax_rate / 100.0), 2)
        item_total = round(taxable_item + item_tax, 2)

        subtotal += item_subtotal
        raw_item_tax += item_tax

        processed_items.append({
            "product_id": item.get("product_id"),
            "product_name": item.get("name") or item.get("product_name"),
            "sku": item.get("sku", ""),
            "unit_price": price,
            "purchase_price": float(item.get("purchase_price", 0.0)),
            "quantity": qty,
            "discount_amount": item_disc,
            "tax_rate": item_tax_rate,
            "tax_amount": item_tax,
            "total_amount": item_total
        })

    subtotal = round(subtotal, 2)
    val = float(discount_value if discount_value is not None else (discount_amount or 0.0))
    disc_type = str(discount_type or "fixed").lower()

    if disc_type == "percentage":
        disc_val = max(0.0, val)
        computed_discount = round(subtotal * (disc_val / 100.0), 2)
    else:
        disc_val = max(0.0, val)
        computed_discount = round(disc_val, 2)

    # Prevent discount from exceeding subtotal
    computed_discount = min(subtotal, computed_discount)
    taxable_amount = max(0.0, round(subtotal - computed_discount, 2))

    # Apply proportional tax on taxable amount
    if subtotal > 0 and computed_discount > 0:
        tax_ratio = taxable_amount / subtotal
        total_tax = round(raw_item_tax * tax_ratio, 2)
    else:
        total_tax = round(raw_item_tax, 2)

    # Proportional split of GST into CGST & SGST (50% each for intra-state)
    cgst = round(total_tax / 2.0, 2)
    sgst = round(total_tax - cgst, 2)
    grand_total = round(taxable_amount + total_tax, 2)

    return {
        "subtotal": subtotal,
        "discount_type": disc_type,
        "discount_value": disc_val,
        "discount_amount": computed_discount,
        "taxable_amount": taxable_amount,
        "tax_amount": round(total_tax, 2),
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "grand_total": grand_total,
        "items": processed_items
    }

def complete_sale(business_id, user_id, items, customer_id=None, customer_name=None, 
                  customer_phone=None, discount_type="fixed", discount_value=0.0, 
                  discount_amount=None, payment_method="cash", paid_amount=None, 
                  notes="", prefix="INV-", tax_enabled=1):
    """
    Executes an atomic POS sale transaction:
    1. Validates inputs & computes precise decimal totals (with percentage or fixed discount)
    2. Generates unique invoice number
    3. Inserts into sales & sale_items
    4. Automatically decrements inventory and logs stock movement
    5. Records initial payment into customer_payments if paid_amount > 0
    6. Updates customer balance if credit/pay later or partial
    """
    if not items or len(items) == 0:
        raise ValueError("Cannot complete sale with an empty cart.")

    # Calculate exact totals
    calc = calculate_cart_totals(
        items, 
        discount_type=discount_type, 
        discount_value=discount_value, 
        discount_amount=discount_amount, 
        tax_enabled=bool(tax_enabled)
    )
    grand_total = calc["grand_total"]

    # Determine paid vs pending balance (Udhar)
    method = str(payment_method or "cash").lower()
    if paid_amount is None:
        if method in ("cash", "upi", "card"):
            actual_paid = grand_total
        else:
            actual_paid = 0.0
    else:
        actual_paid = max(0.0, min(grand_total, float(paid_amount)))

    balance_amount = max(0.0, round(grand_total - actual_paid, 2))
    if balance_amount == 0.0:
        payment_status = "paid"
    elif actual_paid == 0.0:
        payment_status = "unpaid"
    else:
        payment_status = "partial"

    # Require customer identity if outstanding credit/Udhar is created
    if balance_amount > 0 and not customer_id and not customer_phone and (not customer_name or customer_name == "Walk-in Customer"):
        raise ValueError("Customer Name or Phone is required to record outstanding Udhar / Credit.")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        invoice_number = generate_next_invoice_number(business_id, prefix=prefix)

        # 1. Insert into sales
        cur.execute("""
        INSERT INTO sales 
        (business_id, invoice_number, customer_id, customer_name, customer_phone, subtotal, 
         discount_type, discount_value, discount_amount, tax_amount, cgst_amount, sgst_amount, 
         grand_total, paid_amount, balance_amount, payment_method, payment_status, notes, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            business_id, invoice_number, customer_id, customer_name or "Walk-in Customer",
            customer_phone or "", calc["subtotal"], calc["discount_type"], calc["discount_value"],
            calc["discount_amount"], calc["tax_amount"], calc["cgst_amount"], calc["sgst_amount"], 
            grand_total, actual_paid, balance_amount, method, payment_status, notes, user_id
        ))
        sale_id = cur.lastrowid

        # 2. Insert sale_items & decrement stock
        for itm in calc["items"]:
            cost_price = itm["purchase_price"]
            if itm["product_id"]:
                p_row = cur.execute("SELECT purchase_price, stock_quantity FROM products WHERE id = ? AND business_id = ?", 
                                    (itm["product_id"], business_id)).fetchone()
                if p_row:
                    cost_price = p_row["purchase_price"]
                    current_stock = p_row["stock_quantity"]
                    new_stock = max(0.0, current_stock - itm["quantity"])
                    cur.execute("UPDATE products SET stock_quantity = ? WHERE id = ?", (new_stock, itm["product_id"]))
                    cur.execute("""
                    INSERT INTO stock_movements (business_id, product_id, change_qty, new_stock, reason, reference_id, notes)
                    VALUES (?, ?, ?, ?, 'sale', ?, ?)
                    """, (business_id, itm["product_id"], -itm["quantity"], new_stock, invoice_number, f"Sold on {invoice_number}"))

            cur.execute("""
            INSERT INTO sale_items
            (sale_id, product_id, product_name, sku, unit_price, purchase_price, quantity, discount_amount, tax_rate, tax_amount, total_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sale_id, itm["product_id"], itm["product_name"], itm["sku"], itm["unit_price"],
                cost_price, itm["quantity"], itm["discount_amount"], itm["tax_rate"], itm["tax_amount"], itm["total_amount"]
            ))

        # 3. Log initial payment record if amount paid > 0
        if actual_paid > 0:
            cur.execute("""
            INSERT INTO customer_payments (business_id, customer_id, invoice_id, amount, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                business_id,
                customer_id or 0,
                sale_id,
                actual_paid,
                method,
                f"Initial payment received on Invoice {invoice_number}"
            ))

        # 4. Update customer outstanding balance & total spent if customer linked
        if customer_id:
            cur.execute("""
            UPDATE customers 
            SET total_spent = total_spent + ?,
                outstanding_balance = outstanding_balance + ?
            WHERE id = ? AND business_id = ?
            """, (grand_total, balance_amount, customer_id, business_id))

        conn.commit()
        return {
            "sale_id": sale_id,
            "invoice_number": invoice_number,
            "subtotal": calc["subtotal"],
            "discount_type": calc["discount_type"],
            "discount_value": calc["discount_value"],
            "discount_amount": calc["discount_amount"],
            "grand_total": grand_total,
            "paid_amount": actual_paid,
            "balance_amount": balance_amount,
            "payment_status": payment_status
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
