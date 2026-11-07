import sys
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from models.database import init_db, get_db_connection
from services.pos_service import calculate_cart_totals, complete_sale
from services.udhar_service import (
    get_udhar_summary,
    get_udhar_invoices,
    collect_udhar_payment,
    get_customer_udhar_ledger,
    run_udhar_reminders,
    get_notifications,
    mark_notification_read,
    snooze_notification
)
from services.customer_service import create_or_get_customer

def run_all_tests():
    print("=" * 70)
    print("SHOPLEDGER: DISCOUNT, PARTIAL PAYMENT & UDHAR TEST SUITE")
    print("=" * 70)

    init_db()
    conn = get_db_connection()

    # 1. Setup Test Businesses & Users
    conn.execute("DELETE FROM reminder_history")
    conn.execute("DELETE FROM notifications")
    conn.execute("DELETE FROM customer_payments")
    conn.execute("DELETE FROM sale_items")
    conn.execute("DELETE FROM sales")
    conn.execute("DELETE FROM stock_movements")
    conn.execute("DELETE FROM products WHERE sku LIKE 'TEST-%'")
    conn.execute("DELETE FROM customers WHERE phone LIKE '999999999%'")
    conn.execute("DELETE FROM users WHERE email LIKE 'test_%@shopledger.io'")
    conn.execute("DELETE FROM businesses WHERE name LIKE 'Test Shop %'")
    conn.commit()

    # User & Business A
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users (email, password, name, role)
    VALUES ('test_a@shopledger.io', 'hash123', 'Owner A', 'owner')
    """)
    user_a_id = cur.lastrowid

    cur.execute("""
    INSERT INTO businesses (owner_id, name, currency, tax_enabled, invoice_prefix)
    VALUES (?, 'Test Shop A', '₹', 1, 'INV-A-')
    """, (user_a_id,))
    biz_a_id = cur.lastrowid

    cur.execute("UPDATE users SET business_id = ? WHERE id = ?", (biz_a_id, user_a_id))

    # User & Business B (for multi-tenant isolation test)
    cur.execute("""
    INSERT INTO users (email, password, name, role)
    VALUES ('test_b@shopledger.io', 'hash123', 'Owner B', 'owner')
    """)
    user_b_id = cur.lastrowid

    cur.execute("""
    INSERT INTO businesses (owner_id, name, currency, tax_enabled, invoice_prefix)
    VALUES (?, 'Test Shop B', '₹', 1, 'INV-B-')
    """, (user_b_id,))
    biz_b_id = cur.lastrowid

    cur.execute("UPDATE users SET business_id = ? WHERE id = ?", (biz_b_id, user_b_id))

    # Create test products in Biz A
    cur.execute("""
    INSERT INTO products (business_id, name, sku, purchase_price, selling_price, tax_rate, stock_quantity)
    VALUES (?, 'Premium Basmati Rice 5kg', 'TEST-RICE', 300.0, 500.0, 5.0, 50.0)
    """, (biz_a_id,))
    prod_rice_id = cur.lastrowid

    cur.execute("""
    INSERT INTO products (business_id, name, sku, purchase_price, selling_price, tax_rate, stock_quantity)
    VALUES (?, 'Organic Olive Oil 1L', 'TEST-OIL', 600.0, 1000.0, 12.0, 40.0)
    """, (biz_a_id,))
    prod_oil_id = cur.lastrowid

    conn.commit()
    conn.close()

    print(f"[*] Test environment initialized. Biz A #{biz_a_id}, Biz B #{biz_b_id}")

    # =========================================================================
    # TEST 1: Percentage-Based Discount Billing
    # =========================================================================
    print("\n--- TEST 1: Percentage-Based Discount Calculation & Storage ---")
    cart_t1 = [
        {"product_id": prod_oil_id, "name": "Organic Olive Oil 1L", "unit_price": 1000.0, "purchase_price": 600.0, "tax_rate": 0.0, "quantity": 2}
    ]
    # Subtotal: 2 * 1000 = 2000. 10% discount = 200. Grand total = 1800.
    cust_t1 = create_or_get_customer(biz_a_id, name="Rahul Sharma", phone="9999999991")
    sale_t1 = complete_sale(
        business_id=biz_a_id,
        user_id=user_a_id,
        items=cart_t1,
        customer_id=cust_t1["id"],
        customer_name=cust_t1["name"],
        customer_phone=cust_t1["phone"],
        discount_type="percentage",
        discount_value=10.0,
        payment_method="cash",
        tax_enabled=0
    )
    
    conn = get_db_connection()
    row_t1 = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_t1["sale_id"],)).fetchone()
    conn.close()

    assert row_t1["subtotal"] == 2000.0, f"Expected 2000.0, got {row_t1['subtotal']}"
    assert row_t1["discount_type"] == "percentage", f"Expected percentage, got {row_t1['discount_type']}"
    assert row_t1["discount_value"] == 10.0, f"Expected 10.0, got {row_t1['discount_value']}"
    assert row_t1["discount_amount"] == 200.0, f"Expected 200.0, got {row_t1['discount_amount']}"
    assert row_t1["grand_total"] == 1800.0, f"Expected 1800.0, got {row_t1['grand_total']}"
    assert row_t1["payment_status"] == "paid"
    print(" [PASS] TEST 1 passed: Subtotal ₹2,000 with 10% discount = ₹200 discount, grand total ₹1,800 paid in cash.")

    # =========================================================================
    # TEST 2: Fixed (Flat) Discount Billing
    # =========================================================================
    print("\n--- TEST 2: Fixed Amount Discount Billing ---")
    cart_t2 = [
        {"product_id": prod_oil_id, "name": "Organic Olive Oil 1L", "unit_price": 1000.0, "purchase_price": 600.0, "tax_rate": 0.0, "quantity": 2}
    ]
    # Subtotal: 2000. Fixed discount = 150. Grand total = 1850.
    cust_t2 = create_or_get_customer(biz_a_id, name="Amit Patel", phone="9999999992")
    sale_t2 = complete_sale(
        business_id=biz_a_id,
        user_id=user_a_id,
        items=cart_t2,
        customer_id=cust_t2["id"],
        customer_name=cust_t2["name"],
        customer_phone=cust_t2["phone"],
        discount_type="fixed",
        discount_value=150.0,
        payment_method="upi",
        tax_enabled=0
    )

    conn = get_db_connection()
    row_t2 = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_t2["sale_id"],)).fetchone()
    conn.close()

    assert row_t2["discount_type"] == "fixed"
    assert row_t2["discount_amount"] == 150.0
    assert row_t2["grand_total"] == 1850.0
    assert row_t2["paid_amount"] == 1850.0
    assert row_t2["payment_status"] == "paid"
    print(" [PASS] TEST 2 passed: Subtotal ₹2,000 with fixed ₹150 discount = grand total ₹1,850.")

    # =========================================================================
    # TEST 3: Partial Payment (Cash + Udhar)
    # =========================================================================
    print("\n--- TEST 3: Partial Payment (Bill ₹5,000, Paid ₹3,000, Udhar ₹2,000) ---")
    cart_t3 = [
        {"product_id": prod_oil_id, "name": "Organic Olive Oil 1L", "unit_price": 1000.0, "purchase_price": 600.0, "tax_rate": 0.0, "quantity": 5}
    ]
    # Total: 5 * 1000 = 5000. Customer pays 3000 now.
    cust_t3 = create_or_get_customer(biz_a_id, name="Vikas Verma", phone="9999999993")
    sale_t3 = complete_sale(
        business_id=biz_a_id,
        user_id=user_a_id,
        items=cart_t3,
        customer_id=cust_t3["id"],
        customer_name=cust_t3["name"],
        customer_phone=cust_t3["phone"],
        payment_method="partial_cash",
        paid_amount=3000.0,
        tax_enabled=0
    )

    conn = get_db_connection()
    row_t3 = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_t3["sale_id"],)).fetchone()
    c_row_t3 = conn.execute("SELECT outstanding_balance FROM customers WHERE id = ?", (cust_t3["id"],)).fetchone()
    p_rows_t3 = conn.execute("SELECT * FROM customer_payments WHERE invoice_id = ?", (sale_t3["sale_id"],)).fetchall()
    conn.close()

    assert row_t3["grand_total"] == 5000.0
    assert row_t3["paid_amount"] == 3000.0
    assert row_t3["balance_amount"] == 2000.0
    assert row_t3["payment_status"] == "partial"
    assert c_row_t3["outstanding_balance"] == 2000.0
    assert len(p_rows_t3) == 1
    assert p_rows_t3[0]["amount"] == 3000.0
    print(" [PASS] TEST 3 passed: Bill ₹5,000 recorded with ₹3,000 paid, ₹2,000 Udhar, status='partial', customer balance updated.")

    # =========================================================================
    # TEST 4: 100% Pay Later (Credit/Full Udhar)
    # =========================================================================
    print("\n--- TEST 4: 100% Pay Later / Credit (Full Udhar) ---")
    cart_t4 = [
        {"product_id": prod_oil_id, "name": "Organic Olive Oil 1L", "unit_price": 1000.0, "purchase_price": 600.0, "tax_rate": 0.0, "quantity": 4}
    ]
    # Total: 4000. Paid: 0. Balance: 4000.
    cust_t4 = create_or_get_customer(biz_a_id, name="Pooja Mehta", phone="9999999994")
    sale_t4 = complete_sale(
        business_id=biz_a_id,
        user_id=user_a_id,
        items=cart_t4,
        customer_id=cust_t4["id"],
        customer_name=cust_t4["name"],
        customer_phone=cust_t4["phone"],
        payment_method="credit",
        tax_enabled=0
    )

    conn = get_db_connection()
    row_t4 = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_t4["sale_id"],)).fetchone()
    c_row_t4 = conn.execute("SELECT outstanding_balance FROM customers WHERE id = ?", (cust_t4["id"],)).fetchone()
    conn.close()

    assert row_t4["grand_total"] == 4000.0
    assert row_t4["paid_amount"] == 0.0
    assert row_t4["balance_amount"] == 4000.0
    assert row_t4["payment_status"] == "unpaid"
    assert c_row_t4["outstanding_balance"] == 4000.0
    print(" [PASS] TEST 4 passed: 100% Pay Later recorded with ₹0 paid, ₹4,000 balance, status='unpaid'.")

    # =========================================================================
    # TEST 5: Collect Udhar Payment (Settlement)
    # =========================================================================
    print("\n--- TEST 5: Collect Udhar Payment & Automatic Settlement ---")
    # Collect remaining 2000 on sale_t3
    coll_res = collect_udhar_payment(
        business_id=biz_a_id,
        invoice_id=sale_t3["sale_id"],
        amount=2000.0,
        payment_method="upi",
        transaction_ref="UPI/123456789",
        notes="Settled via GPay"
    )

    conn = get_db_connection()
    row_t5 = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_t3["sale_id"],)).fetchone()
    c_row_t5 = conn.execute("SELECT outstanding_balance FROM customers WHERE id = ?", (cust_t3["id"],)).fetchone()
    p_rows_t5 = conn.execute("SELECT * FROM customer_payments WHERE invoice_id = ?", (sale_t3["sale_id"],)).fetchall()
    conn.close()

    assert coll_res["new_balance"] == 0.0
    assert coll_res["payment_status"] == "paid"
    assert row_t5["paid_amount"] == 5000.0
    assert row_t5["balance_amount"] == 0.0
    assert row_t5["payment_status"] == "paid"
    assert c_row_t5["outstanding_balance"] == 0.0
    assert len(p_rows_t5) == 2 # Initial 3000 + collection 2000
    print(" [PASS] TEST 5 passed: ₹2,000 Udhar collection settled invoice to ₹0.00 due, status='paid', customer balance cleared.")

    # =========================================================================
    # TEST 6: Validation & Error Handling
    # =========================================================================
    print("\n--- TEST 6: Validation, Boundaries & Error Handling ---")
    # 6a. Negative or zero payment amount collection
    try:
        collect_udhar_payment(biz_a_id, sale_t4["sale_id"], amount=0.0)
        assert False, "Zero payment amount should have raised ValueError"
    except ValueError as ve:
        print(f" [PASS] 6a: Correctly rejected 0 amount: {ve}")

    # 6b. Payment exceeding outstanding balance
    try:
        collect_udhar_payment(biz_a_id, sale_t4["sale_id"], amount=5000.0)
        assert False, "Overpayment should have raised ValueError"
    except ValueError as ve:
        print(f" [PASS] 6b: Correctly rejected payment > balance: {ve}")

    # 6c. Collecting on already settled invoice
    try:
        collect_udhar_payment(biz_a_id, sale_t3["sale_id"], amount=100.0)
        assert False, "Collection on settled invoice should have raised ValueError"
    except ValueError as ve:
        print(f" [PASS] 6c: Correctly rejected collection on settled invoice: {ve}")

    # 6d. Udhar without customer details
    try:
        complete_sale(
            business_id=biz_a_id,
            user_id=user_a_id,
            items=cart_t4,
            payment_method="credit"
        )
        assert False, "Udhar without customer should have raised ValueError"
    except ValueError as ve:
        print(f" [PASS] 6d: Correctly rejected anonymous credit bill: {ve}")

    # =========================================================================
    # TEST 7: Automatic 5-Day Reminder Engine
    # =========================================================================
    print("\n--- TEST 7: 5-Day Cycle Reminder Engine & Deduplication ---")
    conn = get_db_connection()
    # Backdate sale_t4 to 12 days ago (Cycle 2: Day 10-14)
    twelve_days_ago = (datetime.date.today() - datetime.timedelta(days=12)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE sales SET created_at = ? WHERE id = ?", (twelve_days_ago, sale_t4["sale_id"]))
    conn.commit()
    conn.close()

    # Run reminders
    reminders_created = run_udhar_reminders(biz_a_id)
    assert reminders_created == 1, f"Expected 1 reminder created, got {reminders_created}"

    # Verify notification details
    notifs = get_notifications(biz_a_id)
    assert len(notifs["notifications"]) == 1
    assert "Day 10" in notifs["notifications"][0]["title"]
    assert notifs["unread_count"] == 1

    # Re-run: should deduplicate (0 new reminders)
    reminders_rerun = run_udhar_reminders(biz_a_id)
    assert reminders_rerun == 0, f"Expected 0 duplicates on rerun, got {reminders_rerun}"
    print(" [PASS] TEST 7a passed: Day 10 reminder generated and deduplicated successfully.")

    # Overdue test (> 30 days)
    conn = get_db_connection()
    thirty_five_days_ago = (datetime.date.today() - datetime.timedelta(days=35)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE sales SET created_at = ? WHERE id = ?", (thirty_five_days_ago, sale_t4["sale_id"]))
    conn.commit()
    conn.close()

    reminders_cycle7 = run_udhar_reminders(biz_a_id)
    assert reminders_cycle7 == 1, f"Expected 1 overdue reminder for cycle 7, got {reminders_cycle7}"

    notifs_overdue = get_notifications(biz_a_id, status_filter="overdue")
    assert len(notifs_overdue["notifications"]) == 1
    assert "Overdue" in notifs_overdue["notifications"][0]["title"]
    print(" [PASS] TEST 7b passed: Overdue 35-day alert created with notification_type='overdue'.")

    # Settlement test: settle sale_t4 and verify notifications marked read and no new reminders
    collect_udhar_payment(biz_a_id, sale_t4["sale_id"], amount=4000.0)
    notifs_after_settle = get_notifications(biz_a_id, status_filter="unread")
    assert notifs_after_settle["unread_count"] == 0, "All notifications should be marked read on full settlement"
    reminders_post_settle = run_udhar_reminders(biz_a_id)
    assert reminders_post_settle == 0, "No reminders should be generated for settled invoices"
    print(" [PASS] TEST 7c passed: Settling invoice automatically stopped reminders and archived notifications.")

    # =========================================================================
    # TEST 8: Multi-Tenant Data Isolation
    # =========================================================================
    print("\n--- TEST 8: Multi-Tenant Data Isolation ---")
    # In Biz B, create an invoice
    cust_b = create_or_get_customer(biz_b_id, name="Suresh Gupta", phone="9999999999")
    sale_b = complete_sale(
        business_id=biz_b_id,
        user_id=user_b_id,
        items=[{"product_id": None, "product_name": "Generic Item", "unit_price": 750.0, "purchase_price": 400.0, "tax_rate": 0.0, "quantity": 1}],
        customer_id=cust_b["id"],
        customer_name=cust_b["name"],
        customer_phone=cust_b["phone"],
        payment_method="credit",
        tax_enabled=0
    )

    # Verify Biz A summary does NOT include Biz B's 750
    summary_a = get_udhar_summary(biz_a_id)
    summary_b = get_udhar_summary(biz_b_id)
    assert summary_a["total_outstanding"] == 0.0, f"Biz A should have 0.0 outstanding, got {summary_a['total_outstanding']}"
    assert summary_b["total_outstanding"] == 750.0, f"Biz B should have 750.0 outstanding, got {summary_b['total_outstanding']}"

    # Verify Biz A cannot collect Biz B's invoice
    try:
        collect_udhar_payment(business_id=biz_a_id, invoice_id=sale_b["sale_id"], amount=750.0)
        assert False, "Biz A should NOT be able to collect Biz B's invoice"
    except ValueError as ve:
        print(f" [PASS] Multi-tenant cross-business collection rejected: {ve}")

    print(" [PASS] TEST 8 passed: Multi-tenant database queries and operations strictly isolated.")

    print("\n" + "=" * 70)
    print("ALL 8 UDHAR, DISCOUNT & PARTIAL PAYMENT TEST SCENARIOS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    run_all_tests()
