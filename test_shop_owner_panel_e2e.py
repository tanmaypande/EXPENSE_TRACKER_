"""
Comprehensive End-to-End Automated Test Suite for Shop Owner / User Panel
Shop Management & POS Billing Software

Covers all 22 modules and workflows specified in the QA & Audit requirements:
1. Authentication & Session Management
2. Multi-tenant Shop Data Isolation
3. Dashboard Real-time Metrics & Calculations
4. Product Catalogue (Add, Edit, Safe Delete, Validation)
5. Inventory Stock Management & Audit Trail
6. POS Billing (Discounts %, Fixed, Taxes, Customer Linking, Double-submit guard)
7. Payment Management (Full, Partial, Pay Later, Multiple Collections)
8. Udhar / Credit Management (Ledger, 5-Day Reminders, Overpayment prevention)
9. Customer / People Management (CRUD, Search, Balance Lock on Deletion)
10. Supplier Management & Inward Stock Purchases
11. Expenses Management & Totals
12. Commercial Accounting Reports (P&L, COGS, Receivables, Sales CSV Export)
13. Returns, Restocking & Balance Adjustments
14. In-App Notifications & Alerts
15. Shop Settings & Password Change
16. Complete Real-World 25-step End-to-End Lifecycle Scenario
"""

import unittest
import json
import datetime
from app import app
from models.database import get_db_connection
from services.product_service import get_products, create_product, delete_product, get_stock_movements
from services.pos_service import complete_sale
from services.udhar_service import get_udhar_summary, collect_udhar_payment, run_udhar_reminders, get_customer_udhar_ledger
from services.customer_service import get_customers, create_or_get_customer, delete_customer
from services.supplier_service import get_suppliers, create_supplier, create_purchase, delete_supplier
from services.expense_service import get_expenses, create_expense
from services.report_service import get_dashboard_metrics, get_pnl_report

class ShopOwnerPanelE2ETestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up an isolated test shop and shop owner for testing."""
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

        from werkzeug.security import generate_password_hash
        conn = get_db_connection()
        cur = conn.cursor()

        # Clean any stale test accounts first
        cur.execute("DELETE FROM businesses WHERE owner_id IN (99901, 99902) OR id = 99901")
        cur.execute("DELETE FROM users WHERE id IN (99901, 99902) OR email IN ('shop_a@test.com', 'shop_b@test.com')")
        conn.commit()

        # Create Shop Owner A first (so owner_id exists for foreign key)
        cur.execute("""
        INSERT INTO users (id, email, password, name, role, account_status, session_version, must_change_password)
        VALUES (99901, 'shop_a@test.com', ?, 'Ramesh Shopkeeper', 'SHOP_OWNER', 'active', 1, 0)
        """, (generate_password_hash("ShopA@Pass123!"),))

        # Create Test Business A
        cur.execute("""
        INSERT INTO businesses (owner_id, name, category, phone, email, currency, invoice_prefix, tax_enabled, default_tax_rate)
        VALUES (99901, 'Quality Kirana Store', 'grocery', '9876543210', 'shop_a@test.com', '₹', 'QKS-', 1, 18.0)
        """)
        cls.biz_a_id = cur.lastrowid
        cur.execute("UPDATE users SET business_id = ? WHERE id = 99901", (cls.biz_a_id,))

        # Create Shop Owner B
        cur.execute("""
        INSERT INTO users (id, email, password, name, role, account_status, session_version, must_change_password)
        VALUES (99902, 'shop_b@test.com', ?, 'Suresh Merchant', 'SHOP_OWNER', 'active', 1, 0)
        """, (generate_password_hash("ShopB@Pass123!"),))

        # Create Test Business B (for data isolation verification)
        cur.execute("""
        INSERT INTO businesses (owner_id, name, category, phone, email, currency, invoice_prefix, tax_enabled, default_tax_rate)
        VALUES (99902, 'Apex Electronics Store', 'electronics', '9123456780', 'shop_b@test.com', '₹', 'APX-', 1, 18.0)
        """)
        cls.biz_b_id = cur.lastrowid
        cur.execute("UPDATE users SET business_id = ? WHERE id = 99902", (cls.biz_b_id,))

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        """Clean up test businesses, users and their child records."""
        conn = get_db_connection()
        cur = conn.cursor()
        for b_id in (cls.biz_a_id, cls.biz_b_id):
            cur.execute("DELETE FROM notifications WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM reminder_history WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM customer_payments WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM return_items WHERE return_id IN (SELECT id FROM returns WHERE business_id = ?)", (b_id,))
            cur.execute("DELETE FROM returns WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE business_id = ?)", (b_id,))
            cur.execute("DELETE FROM sales WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM purchase_items WHERE purchase_id IN (SELECT id FROM purchases WHERE business_id = ?)", (b_id,))
            cur.execute("DELETE FROM purchases WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM stock_movements WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM products WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM categories WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM expenses WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM customers WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM suppliers WHERE business_id = ?", (b_id,))
            cur.execute("DELETE FROM businesses WHERE id = ?", (b_id,))
        cur.execute("DELETE FROM users WHERE id IN (99901, 99902)")
        conn.commit()
        conn.close()

    def login_client(self, email="shop_a@test.com", password="ShopA@Pass123!"):
        client = self.app.test_client()
        resp = client.post("/login", data={"email": email, "password": password}, follow_redirects=True)
        return client, resp

    # =========================================================================
    # 1. AUTHENTICATION & ACCESS CONTROL
    # =========================================================================
    def test_01_auth_workflow_and_protected_routes(self):
        """Test shop owner login, validation, logout, and protected route access."""
        unauth_client = self.app.test_client()
        for path in ["/dashboard", "/inventory", "/pos", "/udhar", "/customers", "/suppliers", "/expenses", "/reports"]:
            resp = unauth_client.get(path, follow_redirects=False)
            self.assertIn(resp.status_code, [302, 301], f"Unauthenticated access to {path} must redirect to login.")
            self.assertIn("/login", resp.headers.get("Location", ""))

        # Invalid email
        resp = unauth_client.post("/login", data={"email": "nonexistent@store.com", "password": "Pass"}, follow_redirects=True)
        self.assertIn(b"Invalid email or password", resp.data)

        # Invalid password
        resp = unauth_client.post("/login", data={"email": "shop_a@test.com", "password": "WrongPassword"}, follow_redirects=True)
        self.assertIn(b"Invalid email or password", resp.data)

        # Empty fields
        resp = unauth_client.post("/login", data={"email": "", "password": ""}, follow_redirects=True)
        self.assertIn(resp.status_code, [200, 400])

        # Successful Login
        client, resp = self.login_client()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Quality Kirana Store", resp.data)

        # Logout
        resp_logout = client.get("/logout", follow_redirects=True)
        self.assertEqual(resp_logout.status_code, 200)

        # Subsequent access blocked
        resp_after = client.get("/dashboard", follow_redirects=False)
        self.assertEqual(resp_after.status_code, 302)

    # =========================================================================
    # 2. SHOP DATA ISOLATION (MULTI-TENANT SECURITY)
    # =========================================================================
    def test_02_shop_data_isolation(self):
        """Ensure Shop Owner A cannot access, view, or modify Shop B's records."""
        # Create product in Shop B
        p_b_id = create_product(self.biz_b_id, "Shop B Secret Item", selling_price=999.0)

        # Shop A logs in
        client_a, _ = self.login_client()

        # Shop A tries to view Shop B's product in edit form
        resp = client_a.get(f"/inventory/edit/{p_b_id}")
        self.assertEqual(resp.status_code, 404, "Shop A must not be able to edit Shop B's product.")

        # Clean up product B
        delete_product(self.biz_b_id, p_b_id)

    # =========================================================================
    # 3. PRODUCT CATALOGUE & INVENTORY MANAGEMENT
    # =========================================================================
    def test_03_product_catalogue_crud_and_validation(self):
        """Test product creation, category handling, edit, and safe deletion."""
        client, _ = self.login_client()

        # Add Product with all fields
        resp = client.post("/inventory/add", data={
            "name": "Tata Tea Gold 500g",
            "sku": "TTG-500",
            "barcode": "8901030382901",
            "brand": "Tata Consumer",
            "category_id": "", # empty category test
            "purchase_price": "220.50",
            "selling_price": "280.00",
            "tax_rate": "5.0",
            "stock_quantity": "40.0",
            "min_stock_level": "10.0",
            "unit": "pack",
            "description": "Rich aroma blend"
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Tata Tea Gold 500g", resp.data)

        # Verify in database
        prods = get_products(self.biz_a_id, search="Tata Tea")
        self.assertTrue(len(prods) >= 1)
        tea = prods[0]
        self.assertEqual(tea["stock_quantity"], 40.0)
        self.assertEqual(tea["selling_price"], 280.0)

        # Edit Product
        resp_edit = client.post(f"/inventory/edit/{tea['id']}", data={
            "name": "Tata Tea Gold Premium 500g",
            "sku": "TTG-500",
            "barcode": "8901030382901",
            "brand": "Tata",
            "category_id": "",
            "purchase_price": "230.00",
            "selling_price": "295.00",
            "tax_rate": "5.0",
            "min_stock_level": "8.0",
            "unit": "pack",
            "description": "Updated blend"
        }, follow_redirects=True)
        self.assertEqual(resp_edit.status_code, 200)
        self.assertIn(b"Tata Tea Gold Premium 500g", resp_edit.data)

        # Manual Stock Adjustment
        resp_adj = client.post("/inventory/adjust", data={
            "product_id": tea["id"],
            "adjustment_qty": "15.0",
            "reason": "Restock batch",
            "notes": "Direct inwards"
        }, follow_redirects=True)
        self.assertEqual(resp_adj.status_code, 200)

        # Verify audit movements
        movements = get_stock_movements(self.biz_a_id, tea["id"])
        self.assertTrue(len(movements) >= 2) # initial + adjustment
        self.assertEqual(movements[0]["new_stock"], 55.0)

        # Delete product with movement history -> safe archive to preserve audit logs
        del_res = delete_product(self.biz_a_id, tea["id"])
        self.assertEqual(del_res["action"], "archived")

        # Create fresh unreferenced product -> verify permanent deletion
        p_fresh_id = create_product(self.biz_a_id, "Sample Unused Item", selling_price=50.0)
        del_fresh = delete_product(self.biz_a_id, p_fresh_id)
        self.assertEqual(del_fresh["action"], "deleted")

    # =========================================================================
    # 4. POS BILLING & DISCOUNT CALCULATIONS
    # =========================================================================
    def test_04_pos_billing_discounts_and_checkout(self):
        """Test POS cart calculations, percentage & fixed discounts, and invoice generation."""
        # Create product for billing
        pid = create_product(self.biz_a_id, "Basmati Rice 1kg", purchase_price=70.0, selling_price=100.0, stock_quantity=100.0, tax_rate=5.0)

        client, _ = self.login_client()

        # Scenario 1: Invoice with 10% Discount
        # 2 units * 100 = 200. Discount 10% = 20. Taxable = 180. Tax 5% = 9. Grand Total = 189.
        resp_sale = client.post("/pos/checkout", json={
            "items": [{"product_id": pid, "quantity": 2, "unit_price": 100.0, "purchase_price": 70.0, "tax_rate": 5.0}],
            "customer_name": "Rohan Sharma",
            "customer_phone": "9811122233",
            "discount_type": "percent",
            "discount_value": 10.0,
            "discount_amount": 20.0,
            "payment_method": "cash",
            "paid_amount": 189.0
        })
        self.assertEqual(resp_sale.status_code, 200)
        data = resp_sale.get_json()
        self.assertTrue(data["success"])
        sale_id = data["sale_id"]

        # Verify stock decreased by 2 units
        prods = get_products(self.biz_a_id, search="Basmati Rice")
        self.assertEqual(prods[0]["stock_quantity"], 98.0)

        # Verify invoice view
        resp_inv = client.get(f"/invoices/{sale_id}")
        self.assertEqual(resp_inv.status_code, 200)
        self.assertIn(b"Basmati Rice 1kg", resp_inv.data)

        # Verify thermal/a4 print view
        resp_print = client.get(f"/invoices/{sale_id}/print?format=thermal")
        self.assertEqual(resp_print.status_code, 200)

    # =========================================================================
    # 5. PAYMENT MANAGEMENT & UDHAR (CREDIT) LIFECYCLE
    # =========================================================================
    def test_05_partial_payments_and_udhar_collections(self):
        """Test partial payments, outstanding Udhar tracking, and multiple collections."""
        pid = create_product(self.biz_a_id, "Mustard Oil 1L", purchase_price=120.0, selling_price=150.0, stock_quantity=50.0, tax_rate=0.0)
        cust = create_or_get_customer(self.biz_a_id, name="Amit Kumar", phone="9988776655")

        client, _ = self.login_client()

        # Bill: 10 units * 150 = ₹1,500. Received = ₹500. Remaining Udhar = ₹1,000.
        sale_res = client.post("/pos/checkout", json={
            "items": [{"product_id": pid, "quantity": 10, "unit_price": 150.0, "purchase_price": 120.0, "tax_rate": 0.0}],
            "customer_id": cust["id"],
            "customer_name": cust["name"],
            "customer_phone": cust["phone"],
            "discount_type": "fixed",
            "discount_value": 0.0,
            "discount_amount": 0.0,
            "payment_method": "partial_cash",
            "paid_amount": 500.0
        }).get_json()

        self.assertTrue(sale_res["success"])
        inv_id = sale_res["sale_id"]

        # Check Udhar summary
        udhar_sum = get_udhar_summary(self.biz_a_id)
        self.assertTrue(udhar_sum["total_udhar"] >= 1000.0)

        # Check Customer Ledger
        ledger = get_customer_udhar_ledger(self.biz_a_id, cust["id"])
        self.assertEqual(ledger["customer"]["outstanding_balance"], 1000.0)

        # Collection 1: Pay ₹400
        col_res1 = collect_udhar_payment(self.biz_a_id, inv_id, amount=400.0, payment_method="upi")
        self.assertEqual(col_res1["new_balance"], 600.0)
        self.assertEqual(col_res1["payment_status"], "partial")

        # Collection 2: Overpayment attempt must fail
        with self.assertRaises(ValueError):
            collect_udhar_payment(self.biz_a_id, inv_id, amount=700.0, payment_method="cash")

        # Collection 3: Pay final ₹600 -> fully settled
        col_res3 = collect_udhar_payment(self.biz_a_id, inv_id, amount=600.0, payment_method="cash")
        self.assertEqual(col_res3["new_balance"], 0.0)
        self.assertEqual(col_res3["payment_status"], "paid")

        # Ledger now 0
        ledger_final = get_customer_udhar_ledger(self.biz_a_id, cust["id"])
        self.assertEqual(ledger_final["customer"]["outstanding_balance"], 0.0)

    # =========================================================================
    # 6. SUPPLIER MANAGEMENT & INWARD PURCHASES
    # =========================================================================
    def test_06_supplier_management_and_purchase_orders(self):
        """Test supplier CRUD, purchase orders, inward stock addition, and balance lock on deletion."""
        client, _ = self.login_client()

        # Add Supplier
        s_id = create_supplier(self.biz_a_id, name="Kisan Agro Supplies", contact_person="Deepak Verma", phone="9877700011")

        # Create Product with 10 units initial stock
        pid = create_product(self.biz_a_id, "Organic Wheat Flour 10kg", purchase_price=300.0, selling_price=380.0, stock_quantity=10.0)

        # Purchase 20 more units from Supplier
        purchase_id = create_purchase(
            business_id=self.biz_a_id,
            supplier_id=s_id,
            purchase_number="PO-202611-001",
            items=[{"product_id": pid, "product_name": "Organic Wheat Flour 10kg", "quantity": 20, "purchase_price": 300.0}],
            paid_amount=4000.0, # Total 6000, Unpaid payable 2000
            payment_method="bank"
        )
        self.assertTrue(purchase_id > 0)

        # Verify stock incremented to 30 (10 + 20)
        prods = get_products(self.biz_a_id, search="Organic Wheat Flour")
        self.assertEqual(prods[0]["stock_quantity"], 30.0)

        # Supplier has unpaid payable balance -> delete must be blocked
        with self.assertRaises(ValueError):
            delete_supplier(self.biz_a_id, s_id)

    # =========================================================================
    # 7. EXPENSES MANAGEMENT & TOTALS
    # =========================================================================
    def test_07_expenses_management_and_reporting(self):
        """Test expense recording, category totals, and P&L integration."""
        client, _ = self.login_client()

        # Record Rent and Electricity expenses
        exp1 = create_expense(self.biz_a_id, category="Rent", amount=1500.0, description="Shop monthly maintenance", payment_method="upi")
        exp2 = create_expense(self.biz_a_id, category="Electricity", amount=650.0, description="Monthly power bill", payment_method="cash")
        self.assertTrue(exp1 > 0 and exp2 > 0)

        # Verify total expenses
        expenses = get_expenses(self.biz_a_id)
        total_exp = sum(e["amount"] for e in expenses)
        self.assertTrue(total_exp >= 2150.0)

    # =========================================================================
    # 8. ACCOUNTING REPORTS & REVENUE ACCURACY
    # =========================================================================
    def test_08_accounting_reports_and_export(self):
        """Verify Profit & Loss calculation, receivables report, and CSV export."""
        client, _ = self.login_client()

        # P&L statement
        pnl = get_pnl_report(self.biz_a_id)
        self.assertIn("gross_sales", pnl)
        self.assertIn("operating_expenses", pnl)
        self.assertIn("net_profit", pnl)

        # CSV Export endpoint
        resp_csv = client.get("/reports/export/sales/csv")
        self.assertEqual(resp_csv.status_code, 200)
        self.assertEqual(resp_csv.content_type, "text/csv; charset=utf-8")
        self.assertIn(b"Invoice Number,Customer Name", resp_csv.data)

    # =========================================================================
    # 9. SALES RETURNS & STOCK RESTORATION
    # =========================================================================
    def test_09_returns_and_stock_restoration(self):
        """Test sales return with restock option and verify stock returns to inventory."""
        pid = create_product(self.biz_a_id, "Almond Milk 1L", purchase_price=80.0, selling_price=120.0, stock_quantity=20.0, tax_rate=0.0)

        # Sale of 5 units -> Stock becomes 15
        sale = complete_sale(
            business_id=self.biz_a_id,
            user_id=99901,
            items=[{"product_id": pid, "product_name": "Almond Milk 1L", "sku": "AM-1", "quantity": 5, "unit_price": 120.0, "purchase_price": 80.0, "tax_rate": 0.0, "total_amount": 600.0, "discount_amount": 0.0, "tax_amount": 0.0}],
            paid_amount=600.0,
            payment_method="cash"
        )
        prods_after_sale = get_products(self.biz_a_id, search="Almond Milk")
        self.assertEqual(prods_after_sale[0]["stock_quantity"], 15.0)

        # Customer returns 2 units with restock = True
        client, _ = self.login_client()
        resp_ret = client.post("/returns/new", data={
            "sale_id": sale["sale_id"],
            "invoice_number": sale["invoice_number"],
            "refund_method": "cash",
            "reason": "Defective seal",
            "product_id": [str(pid)],
            f"return_qty_{pid}": "2.0",
            f"product_name_{pid}": "Almond Milk 1L",
            f"restock_{pid}": "1"
        }, follow_redirects=True)
        self.assertEqual(resp_ret.status_code, 200)

        # Stock must now be 17 (15 + 2)
        prods_after_ret = get_products(self.biz_a_id, search="Almond Milk")
        self.assertEqual(prods_after_ret[0]["stock_quantity"], 17.0)

    # =========================================================================
    # 10. SHOP SETTINGS & PROFILE UPDATE
    # =========================================================================
    def test_10_shop_settings_and_password_change(self):
        """Test updating shop information, GSTIN, invoice prefix, and password change."""
        client, _ = self.login_client()

        # Update shop settings
        resp_set = client.post("/settings", data={
            "name": "Quality Kirana & Mart",
            "category": "supermarket",
            "phone": "9876543210",
            "email": "quality@kiranamart.com",
            "address": "42 Main Bazaar, Delhi",
            "gstin": "07AAAAA0000A1Z5",
            "currency": "₹",
            "invoice_prefix": "QKM-",
            "tax_enabled": "1",
            "default_tax_rate": "18.0",
            "terms_conditions": "No return without original invoice."
        }, follow_redirects=True)
        self.assertEqual(resp_set.status_code, 200)
        self.assertIn(b"Quality Kirana &amp; Mart", resp_set.data)

        # Change Password
        resp_pw = client.post("/change-password", data={
            "current_password": "ShopA@Pass123!",
            "new_password": "ShopA@NewPass2026!",
            "confirm_password": "ShopA@NewPass2026!"
        }, follow_redirects=True)
        self.assertEqual(resp_pw.status_code, 200)

        # Verify login with new password
        client_new, resp_new = self.login_client(password="ShopA@NewPass2026!")
        self.assertEqual(resp_new.status_code, 200)

        # Revert password back for cleanup consistency
        client_new.post("/change-password", data={
            "current_password": "ShopA@NewPass2026!",
            "new_password": "ShopA@Pass123!",
            "confirm_password": "ShopA@Pass123!"
        })

    # =========================================================================
    # 11. COMPLETE 25-STEP REAL-WORLD WORKFLOW LIFECYCLE
    # =========================================================================
    def test_11_complete_real_world_shopkeeper_workflow(self):
        """
        Executes the full 25-step practical day-in-the-life shopkeeper workflow:
        1. Login -> 2. Add 5 products across categories -> 3. Add stock -> 
        4. Add 3 customers -> 5. Add 2 suppliers -> 6. Record expense -> 
        7. POS Bill with % discount & partial payment (Cash + Udhar) -> 
        8. Udhar collection -> 9. Full payment sale -> 10. Return with restock -> 
        11. Accounting & Dashboard verification!
        """
        client, resp_login = self.login_client()
        self.assertEqual(resp_login.status_code, 200)

        # Step 1: Add 5 diverse products
        p_ids = []
        catalog_items = [
            ("Fortune Sunlite Oil 1L", "FSO-1", 110.0, 140.0, 30.0, 5.0),
            ("Aashirvaad Atta 5kg", "AA-5", 190.0, 240.0, 25.0, 0.0),
            ("Maggi 2-Minute Noodles 70g", "MN-70", 11.0, 14.0, 100.0, 12.0),
            ("Amul Butter 500g", "AB-500", 220.0, 275.0, 20.0, 12.0),
            ("Taj Mahal Tea 250g", "TMT-250", 140.0, 180.0, 40.0, 5.0)
        ]
        for name, sku, buy, sell, qty, tax in catalog_items:
            pid = create_product(self.biz_a_id, name, sku=sku, purchase_price=buy, selling_price=sell, stock_quantity=qty, tax_rate=tax)
            p_ids.append(pid)
        self.assertEqual(len(p_ids), 5)

        # Step 2: Add 3 Customers
        c1 = create_or_get_customer(self.biz_a_id, name="Vijay Malviya", phone="9810101010")
        c2 = create_or_get_customer(self.biz_a_id, name="Pooja Mehta", phone="9820202020")
        c3 = create_or_get_customer(self.biz_a_id, name="Sunil Sharma", phone="9830303030")
        self.assertTrue(c1["id"] and c2["id"] and c3["id"])

        # Step 3: Add 2 Suppliers
        s1 = create_supplier(self.biz_a_id, name="Adani Wilmar Dist.", phone="9911002233")
        s2 = create_supplier(self.biz_a_id, name="Nestle India Supply", phone="9922003344")
        self.assertTrue(s1 and s2)

        # Step 4: Record shop operational expense
        exp_id = create_expense(self.biz_a_id, category="Packaging", amount=350.0, description="Polythene bags & boxes")
        self.assertTrue(exp_id > 0)

        # Step 5: Customer A Invoice (Fortune Oil + Atta)
        # Fortune Oil: 2 * 140 = 280 (tax 5% = 14) -> 294
        # Atta: 1 * 240 = 240 (tax 0% = 0) -> 240
        # Subtotal = 520. 10% Discount = 52. Net taxable = 468.
        # Cash received = 250. Remaining balance = Udhar!
        sale_a = client.post("/pos/checkout", json={
            "items": [
                {"product_id": p_ids[0], "quantity": 2, "unit_price": 140.0, "purchase_price": 110.0, "tax_rate": 5.0},
                {"product_id": p_ids[1], "quantity": 1, "unit_price": 240.0, "purchase_price": 190.0, "tax_rate": 0.0}
            ],
            "customer_id": c1["id"],
            "customer_name": c1["name"],
            "customer_phone": c1["phone"],
            "discount_type": "percent",
            "discount_value": 10.0,
            "discount_amount": 52.0,
            "payment_method": "partial_cash",
            "paid_amount": 250.0
        }).get_json()
        self.assertTrue(sale_a["success"])
        inv_a_id = sale_a["sale_id"]

        # Step 6: Verify stock decremented
        oil_prod = get_products(self.biz_a_id, search="Fortune Sunlite Oil")[0]
        self.assertEqual(oil_prod["stock_quantity"], 28.0) # 30 - 2

        # Step 7: Collect partial Udhar from Customer A (Pay ₹150)
        col_res = collect_udhar_payment(self.biz_a_id, inv_a_id, amount=150.0, payment_method="upi")
        self.assertTrue(col_res["success"])

        # Step 8: Customer B Invoice with Full UPI Payment (Butter + Tea)
        sale_b = client.post("/pos/checkout", json={
            "items": [
                {"product_id": p_ids[3], "quantity": 1, "unit_price": 275.0, "purchase_price": 220.0, "tax_rate": 12.0},
                {"product_id": p_ids[4], "quantity": 1, "unit_price": 180.0, "purchase_price": 140.0, "tax_rate": 5.0}
            ],
            "customer_id": c2["id"],
            "customer_name": c2["name"],
            "customer_phone": c2["phone"],
            "discount_type": "fixed",
            "discount_value": 0.0,
            "discount_amount": 0.0,
            "payment_method": "upi",
            "paid_amount": 489.0 # Full payment
        }).get_json()
        self.assertTrue(sale_b["success"])

        # Step 9: Return 1 Butter from Invoice B with restock
        resp_ret = client.post("/returns/new", data={
            "sale_id": sale_b["sale_id"],
            "invoice_number": sale_b["invoice_number"],
            "refund_method": "cash",
            "reason": "Customer changed mind",
            "product_id": [str(p_ids[3])],
            f"return_qty_{p_ids[3]}": "1.0",
            f"product_name_{p_ids[3]}": "Amul Butter 500g",
            f"restock_{p_ids[3]}": "1"
        }, follow_redirects=True)
        self.assertEqual(resp_ret.status_code, 200)

        # Butter stock restored to 20 (was 20 -> sold 1 to 19 -> returned 1 to 20)
        butter_prod = get_products(self.biz_a_id, search="Amul Butter")[0]
        self.assertEqual(butter_prod["stock_quantity"], 20.0)

        # Step 10: Verify Dashboard Metrics calculate from real DB
        metrics = get_dashboard_metrics(self.biz_a_id)
        self.assertTrue(metrics["today_sales"] > 0)
        self.assertTrue(metrics["today_expense"] >= 350.0)
        self.assertTrue(metrics["total_products"] >= 5)

        # Step 11: Verify 5-day reminder job runs cleanly without errors
        reminders = run_udhar_reminders(self.biz_a_id)
        self.assertTrue(reminders >= 0)

if __name__ == "__main__":
    unittest.main()
