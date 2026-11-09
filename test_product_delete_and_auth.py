import sys
import datetime
from app import app
from models.database import init_db, get_db_connection
from services.product_service import create_product, delete_product, get_products, get_product_by_id
from services.pos_service import complete_sale
from services.customer_service import create_or_get_customer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_product_delete_and_auth():
    print("=" * 70)
    print("TEST SUITE: PRODUCT DELETE & REGISTRATION RESTRICTION")
    print("=" * 70)

    init_db()
    conn = get_db_connection()

    # Find or setup test user & business
    user = conn.execute("SELECT u.id, u.email, u.name, u.business_id, b.name as biz_name FROM users u JOIN businesses b ON u.business_id = b.id LIMIT 1").fetchone()
    if not user:
        from werkzeug.security import generate_password_hash
        cur = conn.cursor()
        cur.execute("INSERT INTO users (email, password, name, role, account_status) VALUES ('temp_tester@shopledger.io', ?, 'Tester', 'SHOP_OWNER', 'active')", (generate_password_hash('test1234'),))
        u_id = cur.lastrowid
        cur.execute("INSERT INTO businesses (owner_id, name, status) VALUES (?, 'Test Shop Mart', 'active')", (u_id,))
        b_id = cur.lastrowid
        cur.execute("UPDATE users SET business_id = ? WHERE id = ?", (b_id, u_id))
        conn.commit()
        user = conn.execute("SELECT u.id, u.email, u.name, u.business_id, b.name as biz_name FROM users u JOIN businesses b ON u.business_id = b.id WHERE u.id = ?", (u_id,)).fetchone()
    conn.close()

    biz_id = user["business_id"]
    user_id = user["id"]
    print(f"[*] Testing with Business #{biz_id} ({user['biz_name']}), User #{user_id}")

    # ---------------------------------------------------------
    # TEST 1: Delete an Unused Product from Inventory (Permanent delete)
    # ---------------------------------------------------------
    print("\n--- TEST 1: Delete Unused Product from Inventory ---")
    p1_id = create_product(
        business_id=biz_id,
        name="Test Delete Unused Product",
        sku="TEST-DEL-01",
        purchase_price=50.0,
        selling_price=100.0,
        stock_quantity=10.0
    )
    # Verify product exists in active catalog
    active_prods = get_products(biz_id, search="TEST-DEL-01")
    assert len(active_prods) == 1, "Product should exist before deletion"

    # Delete unused product
    res1 = delete_product(biz_id, p1_id)
    assert res1["success"] is True
    assert res1["action"] == "deleted", f"Expected action 'deleted', got {res1['action']}"

    # Verify it disappeared from active inventory & catalogue
    active_after = get_products(biz_id, search="TEST-DEL-01")
    assert len(active_after) == 0, "Product must not appear in active inventory after deletion"

    conn = get_db_connection()
    row1 = conn.execute("SELECT * FROM products WHERE id = ?", (p1_id,)).fetchone()
    conn.close()
    assert row1 is None, "Unused product should be permanently removed from DB"
    print(" [PASS] TEST 1 passed: Unused product permanently deleted, disappears from active catalog.")

    # ---------------------------------------------------------
    # TEST 2: Archive / Soft Delete a Product Referenced by an Invoice
    # ---------------------------------------------------------
    print("\n--- TEST 2: Safe Deletion of Referenced Product (Historical Integrity) ---")
    p2_id = create_product(
        business_id=biz_id,
        name="Test Delete Referenced Product",
        sku="TEST-DEL-02",
        purchase_price=80.0,
        selling_price=150.0,
        stock_quantity=20.0
    )

    # Create a customer & sale invoice referencing p2
    cust = create_or_get_customer(biz_id, name="Test History Customer", phone="9999988881")
    sale = complete_sale(
        business_id=biz_id,
        user_id=user_id,
        items=[{"product_id": p2_id, "name": "Test Delete Referenced Product", "unit_price": 150.0, "purchase_price": 80.0, "tax_rate": 0.0, "quantity": 2}],
        customer_id=cust["id"],
        customer_name=cust["name"],
        customer_phone=cust["phone"],
        payment_method="cash",
        paid_amount=300.0,
        tax_enabled=0
    )
    sale_id = sale["sale_id"]

    # Delete referenced product: must be soft-deleted / archived
    res2 = delete_product(biz_id, p2_id)
    assert res2["success"] is True
    assert res2["action"] == "archived", f"Expected action 'archived', got {res2['action']}"

    # Verify it does NOT appear in active inventory/catalog
    active_prods_p2 = get_products(biz_id, search="TEST-DEL-02")
    assert len(active_prods_p2) == 0, "Archived product must not appear in active catalog"

    # Verify historical invoice remains 100% intact
    conn = get_db_connection()
    sale_item = conn.execute("SELECT * FROM sale_items WHERE sale_id = ? AND product_id = ?", (sale_id, p2_id)).fetchone()
    sale_row = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    prod_row = conn.execute("SELECT is_active, deleted_at, stock_quantity FROM products WHERE id = ?", (p2_id,)).fetchone()
    conn.close()

    assert sale_item is not None, "Sale item record must be preserved for invoice history"
    assert sale_item["product_name"] == "Test Delete Referenced Product"
    assert sale_row["grand_total"] == 300.0, "Invoice grand total must remain accurate"
    assert prod_row["is_active"] == 0, "Product is_active must be 0"
    assert prod_row["deleted_at"] is not None, "deleted_at timestamp must be recorded"
    print(" [PASS] TEST 2 passed: Referenced product archived safely (is_active=0), invoice history 100% intact.")

    # ---------------------------------------------------------
    # TEST 3: Unauthorized & Cross-Business Product Deletion Blocked
    # ---------------------------------------------------------
    print("\n--- TEST 3: Unauthorized Deletion Blocked ---")
    try:
        # Attempt to delete using wrong business_id (e.g. 999999)
        delete_product(business_id=999999, product_id=p2_id)
        assert False, "Cross-business deletion should have raised ValueError"
    except ValueError as ve:
        print(f" [PASS] TEST 3 passed: Cross-business deletion blocked: {ve}")

    # ---------------------------------------------------------
    # TEST 4: HTTP Routes Verification (Inventory, Products, Delete API)
    # ---------------------------------------------------------
    print("\n--- TEST 4: HTTP Endpoints for Inventory / Products & Delete API ---")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["user_email"] = user["email"]
        sess["user_name"] = user["name"]
        sess["business_id"] = user["business_id"]
        sess["business_name"] = user["biz_name"]

    # Verify /inventory and /products both work and return HTTP 200
    res_inv = client.get("/inventory")
    assert res_inv.status_code == 200, f"/inventory status: {res_inv.status_code}"
    res_prod = client.get("/products")
    assert res_prod.status_code == 200, f"/products status: {res_prod.status_code}"
    res_cat = client.get("/catalogue")
    assert res_cat.status_code == 200, f"/catalogue status: {res_cat.status_code}"
    print(" [PASS] TEST 4a: /inventory, /products, and /catalogue all route properly (HTTP 200).")

    # Create another product to delete via HTTP POST
    p3_id = create_product(business_id=biz_id, name="Test HTTP Delete Product", sku="TEST-DEL-03", stock_quantity=5.0)
    res_del_post = client.post(f"/inventory/delete/{p3_id}", headers={"Accept": "application/json"})
    assert res_del_post.status_code == 200
    json_data = res_del_post.get_json()
    assert json_data["success"] is True
    print(f" [PASS] TEST 4b: POST /inventory/delete/{p3_id} returned success via JSON API.")

    # ---------------------------------------------------------
    # TEST 5: Verify Create Account Option Removed & Public Registration Blocked
    # ---------------------------------------------------------
    print("\n--- TEST 5: Public Registration Inaccessible & Login Form Clean ---")
    unauth_client = app.test_client()

    # Verify Login page has NO signup link
    res_login = unauth_client.get("/login")
    assert res_login.status_code == 200
    login_html = res_login.get_data(as_text=True)
    assert "Register shop" not in login_html, "Registration link must be removed from login screen"
    assert "Sign up" not in login_html, "Sign up link must be removed from login screen"
    assert "auth-btn-submit" in login_html, "Login submit button must exist"
    print(" [PASS] TEST 5a: Login screen has no registration or create account link.")

    # Verify public registration attempt (POST /signup) is rejected with 403 Forbidden
    res_signup_post = unauth_client.post("/signup", data={"email": "attacker@evil.com", "password": "password123", "name": "Attacker"})
    assert res_signup_post.status_code == 403, f"Expected 403 Forbidden on public signup, got {res_signup_post.status_code}"
    print(" [PASS] TEST 5b: Public POST /signup is blocked with HTTP 403 Forbidden.")

    # Verify GET /signup redirects to /login
    res_signup_get = unauth_client.get("/signup")
    assert res_signup_get.status_code == 302
    assert "/login" in res_signup_get.headers.get("Location", "")
    print(" [PASS] TEST 5c: Public GET /signup redirects to /login.")

    # Verify existing user can still log in successfully
    res_auth = unauth_client.post("/login", data={"email": user["email"], "password": "wrongpassword"})
    assert "Invalid email or password" in res_auth.get_data(as_text=True)
    res_auth_ok = unauth_client.post("/login", data={"email": user["email"], "password": "test1234"})
    assert res_auth_ok.status_code == 302, "Valid credentials should log in and redirect"
    print(" [PASS] TEST 5d: Existing user authentication intact and functioning.")

    # Cleanup temporary test user and business
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE business_id = ?", (biz_id,))
    conn.execute("DELETE FROM businesses WHERE id = ?", (biz_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    print("\n" + "=" * 70)
    print("ALL PRODUCT DELETE & AUTHENTICATION TESTS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    test_product_delete_and_auth()
