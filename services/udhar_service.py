import datetime
from models.database import get_db_connection

def get_udhar_summary(business_id):
    """
    Computes real-time KPI metrics for Udhar Management:
    1. Total Outstanding Udhar (Receivables)
    2. Total Customers with Pending Balances
    3. Amount Collected This Month
    4. Overdue Payments (> 30 days old)
    """
    conn = get_db_connection()
    
    # 1. Total Outstanding Udhar
    row = conn.execute("""
    SELECT COALESCE(SUM(balance_amount), 0.0) 
    FROM sales 
    WHERE business_id = ? AND balance_amount > 0
    """, (business_id,)).fetchone()
    total_outstanding = float(row[0] if row else 0.0)

    # 2. Total Customers with Pending Balances
    row = conn.execute("""
    SELECT COUNT(DISTINCT customer_id) 
    FROM sales 
    WHERE business_id = ? AND balance_amount > 0 AND customer_id IS NOT NULL
    """, (business_id,)).fetchone()
    pending_customers = int(row[0] if row else 0)

    # 3. Amount Collected This Month
    current_month_prefix = datetime.date.today().strftime("%Y-%m")
    row = conn.execute("""
    SELECT COALESCE(SUM(amount), 0.0) 
    FROM customer_payments 
    WHERE business_id = ? AND strftime('%Y-%m', created_at) = ?
    """, (business_id, current_month_prefix)).fetchone()
    collected_this_month = float(row[0] if row else 0.0)

    # 4. Overdue Payments (> 30 days pending)
    thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    row = conn.execute("""
    SELECT COALESCE(SUM(balance_amount), 0.0), COUNT(*) 
    FROM sales 
    WHERE business_id = ? AND balance_amount > 0 AND date(created_at) < ?
    """, (business_id, thirty_days_ago)).fetchone()
    overdue_amount = float(row[0] if row else 0.0)
    overdue_count = int(row[1] if row else 0)

    # Status counts
    row_part = conn.execute("SELECT COUNT(*) FROM sales WHERE business_id = ? AND payment_status = 'partial'", (business_id,)).fetchone()
    row_unpaid = conn.execute("SELECT COUNT(*) FROM sales WHERE business_id = ? AND payment_status = 'unpaid'", (business_id,)).fetchone()
    row_paid = conn.execute("SELECT COUNT(*) FROM sales WHERE business_id = ? AND payment_status = 'paid'", (business_id,)).fetchone()

    conn.close()

    return {
        "total_outstanding": round(total_outstanding, 2),
        "pending_customers": pending_customers,
        "collected_this_month": round(collected_this_month, 2),
        "overdue_amount": round(overdue_amount, 2),
        "overdue_count": overdue_count,
        "partial_invoices_count": row_part[0] if row_part else 0,
        "unpaid_invoices_count": row_unpaid[0] if row_unpaid else 0,
        "paid_invoices_count": row_paid[0] if row_paid else 0,
    }

def get_udhar_invoices(business_id, search=None, status_filter="all", sort_by="balance_desc"):
    """
    Returns customer-wise Udhar invoices with payment statuses and due tracking.
    """
    conn = get_db_connection()
    today = datetime.date.today()
    thirty_days_ago = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")

    base_query = """
    SELECT s.id, s.invoice_number, s.customer_id, s.customer_name, s.customer_phone,
           s.grand_total, s.paid_amount, s.balance_amount, s.payment_method, s.payment_status,
           s.created_at,
           (SELECT MAX(created_at) FROM customer_payments WHERE invoice_id = s.id) as last_payment_date
    FROM sales s
    WHERE s.business_id = ?
    """
    params = [business_id]

    if status_filter == "pending":
        base_query += " AND s.balance_amount > 0"
    elif status_filter == "partial":
        base_query += " AND s.payment_status = 'partial' AND s.balance_amount > 0"
    elif status_filter == "unpaid":
        base_query += " AND s.payment_status = 'unpaid' AND s.balance_amount > 0"
    elif status_filter == "overdue":
        base_query += " AND s.balance_amount > 0 AND date(s.created_at) < ?"
        params.append(thirty_days_ago)
    elif status_filter == "paid":
        base_query += " AND s.balance_amount = 0"
    else:
        # 'all': default show all invoices that have/had credit or are pending first
        pass

    if search:
        s = f"%{search.strip()}%"
        base_query += " AND (s.customer_name LIKE ? OR s.customer_phone LIKE ? OR s.invoice_number LIKE ?)"
        params.extend([s, s, s])

    # Sorting
    if sort_by == "balance_asc":
        base_query += " ORDER BY s.balance_amount ASC, s.created_at DESC"
    elif sort_by == "date_asc":
        base_query += " ORDER BY s.created_at ASC"
    elif sort_by == "date_desc":
        base_query += " ORDER BY s.created_at DESC"
    elif sort_by == "name_asc":
        base_query += " ORDER BY s.customer_name ASC"
    else:
        # Default: Highest remaining balance first
        base_query += " ORDER BY s.balance_amount DESC, s.created_at DESC"

    rows = conn.execute(base_query, params).fetchall()
    conn.close()

    invoices = []
    for r in rows:
        d = dict(r)
        created_str = str(d["created_at"])[:10]
        try:
            bill_date = datetime.date.fromisoformat(created_str)
            days_elapsed = (today - bill_date).days
        except Exception:
            days_elapsed = 0

        d["days_elapsed"] = days_elapsed
        d["is_overdue"] = (days_elapsed >= 30 and d["balance_amount"] > 0)
        if d["is_overdue"]:
            d["due_status"] = "overdue"
        elif d["balance_amount"] == 0:
            d["due_status"] = "paid"
        elif d["paid_amount"] > 0:
            d["due_status"] = "partial"
        else:
            d["due_status"] = "unpaid"

        invoices.append(d)

    return invoices

def collect_udhar_payment(business_id, invoice_id, amount, payment_method="cash", notes="", transaction_ref=""):
    """
    Collects a payment against an outstanding invoice.
    Atomic transaction:
      1. Validates invoice & payment amount
      2. Inserts record into customer_payments
      3. Increments paid_amount, decrements balance_amount on sales
      4. If balance reaches 0, sets payment_status = 'paid'
      5. Decrements customer's outstanding_balance
      6. Marks associated active notifications as read
    """
    amt = round(float(amount or 0.0), 2)
    if amt <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN IMMEDIATE")
        sale = cur.execute("""
        SELECT id, invoice_number, customer_id, customer_name, grand_total, paid_amount, balance_amount, payment_status
        FROM sales 
        WHERE id = ? AND business_id = ?
        """, (invoice_id, business_id)).fetchone()

        if not sale:
            raise ValueError(f"Invoice #{invoice_id} not found.")

        current_balance = round(float(sale["balance_amount"] or 0.0), 2)
        if current_balance <= 0:
            raise ValueError(f"Invoice {sale['invoice_number']} is already fully settled (₹0.00 due).")

        if amt > current_balance:
            raise ValueError(f"Payment amount (₹{amt:.2f}) cannot exceed current outstanding balance (₹{current_balance:.2f}).")

        new_paid = round(float(sale["paid_amount"] or 0.0) + amt, 2)
        new_balance = max(0.0, round(current_balance - amt, 2))
        new_status = "paid" if new_balance == 0.0 else "partial"

        # 1. Update sales record
        cur.execute("""
        UPDATE sales 
        SET paid_amount = ?, balance_amount = ?, payment_status = ?
        WHERE id = ? AND business_id = ?
        """, (new_paid, new_balance, new_status, invoice_id, business_id))

        # 2. Record payment voucher in customer_payments
        cur.execute("""
        INSERT INTO customer_payments 
        (business_id, customer_id, invoice_id, amount, payment_method, transaction_reference, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            business_id,
            sale["customer_id"] or 0,
            invoice_id,
            amt,
            payment_method.lower(),
            transaction_ref.strip(),
            notes.strip() or f"Udhar collection on {sale['invoice_number']}"
        ))
        payment_id = cur.lastrowid

        # 3. Update customer outstanding balance
        if sale["customer_id"]:
            cur.execute("""
            UPDATE customers 
            SET outstanding_balance = MAX(0.0, round(outstanding_balance - ?, 2))
            WHERE id = ? AND business_id = ?
            """, (amt, sale["customer_id"], business_id))

        # 4. If fully paid, mark notifications for this invoice as read
        if new_balance == 0.0:
            cur.execute("""
            UPDATE notifications 
            SET status = 'read' 
            WHERE invoice_id = ? AND business_id = ?
            """, (invoice_id, business_id))

        conn.commit()

        return {
            "success": True,
            "invoice_id": invoice_id,
            "invoice_number": sale["invoice_number"],
            "collected_amount": amt,
            "previous_balance": current_balance,
            "new_balance": new_balance,
            "payment_status": new_status,
            "payment_id": payment_id
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_customer_udhar_ledger(business_id, customer_id):
    """
    Returns complete transaction-level Udhar ledger for a single customer.
    Shows every pending & settled invoice, and every payment receipt voucher.
    """
    conn = get_db_connection()
    customer = conn.execute("""
    SELECT * FROM customers WHERE id = ? AND business_id = ?
    """, (customer_id, business_id)).fetchone()

    if not customer:
        conn.close()
        return None

    c_dict = dict(customer)

    # Invoices for this customer
    invoices_raw = conn.execute("""
    SELECT id, invoice_number, grand_total, paid_amount, balance_amount, 
           payment_method, payment_status, created_at,
           (SELECT MAX(created_at) FROM customer_payments WHERE invoice_id = sales.id) as last_payment_date
    FROM sales
    WHERE customer_id = ? AND business_id = ?
    ORDER BY created_at DESC
    """, (customer_id, business_id)).fetchall()

    today = datetime.date.today()
    invoices = []
    total_purchases = 0.0
    total_paid = 0.0
    total_udhar = 0.0
    total_overdue = 0.0

    for inv in invoices_raw:
        d = dict(inv)
        total_purchases += d["grand_total"]
        total_paid += d["paid_amount"]
        total_udhar += d["balance_amount"]

        created_str = str(d["created_at"])[:10]
        try:
            bill_date = datetime.date.fromisoformat(created_str)
            days_elapsed = (today - bill_date).days
        except Exception:
            days_elapsed = 0

        d["days_elapsed"] = days_elapsed
        d["is_overdue"] = (days_elapsed >= 30 and d["balance_amount"] > 0)
        if d["is_overdue"]:
            total_overdue += d["balance_amount"]

        invoices.append(d)

    # Payments history
    payments_raw = conn.execute("""
    SELECT cp.id, cp.amount, cp.payment_method, cp.transaction_reference, cp.notes, cp.created_at,
           s.invoice_number
    FROM customer_payments cp
    LEFT JOIN sales s ON cp.invoice_id = s.id
    WHERE cp.customer_id = ? AND cp.business_id = ?
    ORDER BY cp.created_at DESC
    """, (customer_id, business_id)).fetchall()

    conn.close()

    return {
        "customer": c_dict,
        "total_purchases": round(total_purchases, 2),
        "total_paid": round(total_paid, 2),
        "total_udhar": round(total_udhar, 2),
        "total_overdue": round(total_overdue, 2),
        "invoices": invoices,
        "payments": [dict(p) for p in payments_raw]
    }

# =========================================================================
# AUTOMATIC 5-DAY REMINDER & NOTIFICATION ENGINE
# =========================================================================

def run_udhar_reminders(business_id=None):
    """
    Backend scheduled job:
    1. Scans all invoices with outstanding balances (Udhar > 0).
    2. Calculates days elapsed since invoice creation.
    3. Triggers a reminder after every 5 days (Day 5, Day 10, Day 15, Day 20, etc.).
    4. Automatically stops when balance reaches 0.
    5. Deduplicates: ensures no duplicate notification is generated for the same invoice & cycle.
    6. Stores in notifications & reminder_history.
    """
    conn = get_db_connection()
    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")

    query = """
    SELECT s.id, s.business_id, s.invoice_number, s.customer_id, s.customer_name, 
           s.customer_phone, s.balance_amount, s.created_at, b.name as business_name
    FROM sales s
    JOIN businesses b ON s.business_id = b.id
    WHERE s.balance_amount > 0
    """
    params = []
    if business_id is not None:
        query += " AND s.business_id = ?"
        params.append(business_id)

    sales = conn.execute(query, params).fetchall()
    reminders_created = 0

    for s in sales:
        created_str = str(s["created_at"])[:10]
        try:
            bill_date = datetime.date.fromisoformat(created_str)
            days_elapsed = (today - bill_date).days
        except Exception:
            continue

        if days_elapsed < 5:
            continue

        # Cycle: 1 for Day 5-9, 2 for Day 10-14, 3 for Day 15-19, etc.
        cycle = days_elapsed // 5
        biz_id = s["business_id"]
        inv_id = s["id"]

        # Check if reminder already created for this cycle
        existing = conn.execute("""
        SELECT 1 FROM reminder_history 
        WHERE business_id = ? AND invoice_id = ? AND reminder_cycle = ?
        """, (biz_id, inv_id, cycle)).fetchone()

        if existing:
            continue

        # Build notification details
        cust_name = s["customer_name"] or "Customer"
        bal_fmt = f"{s['balance_amount']:,.2f}"
        inv_no = s["invoice_number"]
        is_overdue = days_elapsed >= 30

        notif_type = "overdue" if is_overdue else "udhar_reminder"
        title = f"Overdue Payment Alert ({days_elapsed}d)" if is_overdue else f"Udhar Reminder (Day {cycle * 5})"
        message = f"Payment Reminder: {cust_name} has ₹{bal_fmt} pending against Invoice {inv_no}."

        cur = conn.cursor()
        cur.execute("""
        INSERT INTO notifications 
        (business_id, customer_id, invoice_id, notification_type, title, message, amount, reminder_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unread')
        """, (biz_id, s["customer_id"], inv_id, notif_type, title, message, s["balance_amount"], today_str))
        notif_id = cur.lastrowid

        cur.execute("""
        INSERT INTO reminder_history 
        (business_id, invoice_id, reminder_cycle, reminder_date, notification_id)
        VALUES (?, ?, ?, ?, ?)
        """, (biz_id, inv_id, cycle, today_str, notif_id))

        reminders_created += 1

    conn.commit()
    conn.close()
    return reminders_created

def get_notifications(business_id, status_filter="all", limit=50):
    """
    Returns in-app notifications for the business with unread counts.
    """
    conn = get_db_connection()
    base_query = """
    SELECT n.*, s.invoice_number, c.name as cust_name, c.phone as cust_phone
    FROM notifications n
    LEFT JOIN sales s ON n.invoice_id = s.id
    LEFT JOIN customers c ON n.customer_id = c.id
    WHERE n.business_id = ?
    """
    params = [business_id]

    if status_filter == "unread":
        base_query += " AND n.status = 'unread'"
    elif status_filter == "pending":
        base_query += " AND n.notification_type = 'udhar_reminder' AND n.status != 'read'"
    elif status_filter == "overdue":
        base_query += " AND n.notification_type = 'overdue' AND n.status != 'read'"
    elif status_filter == "read":
        base_query += " AND n.status = 'read'"

    base_query += " ORDER BY n.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(base_query, params).fetchall()

    unread_row = conn.execute("""
    SELECT COUNT(*) FROM notifications WHERE business_id = ? AND status = 'unread'
    """, (business_id,)).fetchone()
    unread_count = unread_row[0] if unread_row else 0

    conn.close()
    return {
        "notifications": [dict(r) for r in rows],
        "unread_count": unread_count
    }

def mark_notification_read(business_id, notification_id):
    conn = get_db_connection()
    conn.execute("""
    UPDATE notifications SET status = 'read' WHERE id = ? AND business_id = ?
    """, (notification_id, business_id))
    conn.commit()
    conn.close()
    return True

def snooze_notification(business_id, notification_id, days=5):
    conn = get_db_connection()
    new_date = (datetime.date.today() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    conn.execute("""
    UPDATE notifications SET status = 'snoozed', reminder_date = ? WHERE id = ? AND business_id = ?
    """, (new_date, notification_id, business_id))
    conn.commit()
    conn.close()
    return True
