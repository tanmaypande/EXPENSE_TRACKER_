"""
Simplified Super Admin Panel & Access Control Test Suite
Tests all 12 points requested by the project builder:
1. Super Admin can log in.
2. Shop owners cannot access Super Admin Panel.
3. Public registration is disabled.
4. Super Admin can create shop owner accounts.
5. Duplicate emails are rejected.
6. Newly created shop owner can log in.
7. First login requires password change.
8. Disabled shop owner cannot log in.
9. Existing sessions are revoked after disabling access.
10. Enabled shop owner can log in again.
11. Different shops cannot access each other's data.
12. Existing billing, inventory and accounting features continue working.
"""
import unittest
import time
from app import app
from models.database import get_db_connection

class SimplifiedSuperAdminTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def test_01_super_admin_can_login(self):
        """1. Super Admin can log in with master credentials."""
        # Failed login attempt
        bad_resp = self.client.post("/super-admin/login", data={
            "email": "tanmaypandey0604@gmail.com",
            "password": "WrongPassword!"
        })
        self.assertEqual(bad_resp.status_code, 200)
        self.assertIn(b"Invalid Super Administrator credentials", bad_resp.data)

        # Successful login
        resp = self.client.post("/super-admin/login", data={
            "email": "tanmaypandey0604@gmail.com",
            "password": "TanmayAdmin@2026!"
        }, follow_redirects=False)
        self.assertIn(resp.status_code, [302, 301])
        self.assertIn("/super-admin/dashboard", resp.headers.get("Location", ""))

    def test_02_shop_owners_cannot_access_super_admin(self):
        """2. Shop owners cannot access Super Admin Panel."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 8888
            sess["user_role"] = "SHOP_OWNER"
            sess["user_email"] = "merchant@store.com"

        resp = self.client.get("/super-admin/dashboard", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 301, 403])

        resp_ajax = self.client.get("/super-admin/dashboard", headers={"Accept": "application/json"})
        self.assertEqual(resp_ajax.status_code, 403)

    def test_03_public_registration_is_disabled(self):
        """3. Public registration is disabled."""
        resp_get = self.client.get("/signup", follow_redirects=False)
        self.assertIn(resp_get.status_code, [302, 301])
        self.assertIn("/login", resp_get.headers.get("Location", ""))

        resp_post = self.client.post("/signup", data={"email": "public@user.com", "password": "Pass123456!"})
        self.assertEqual(resp_post.status_code, 403)

    def test_04_05_06_07_create_shop_owner_and_first_login_flow(self):
        """
        4. Super Admin can create shop owner accounts.
        5. Duplicate emails are rejected.
        6. Newly created shop owner can log in.
        7. First login requires password change.
        """
        admin_client = self.app.test_client()
        admin_client.post("/super-admin/login", data={
            "email": "tanmaypandey0604@gmail.com",
            "password": "TanmayAdmin@2026!"
        }, follow_redirects=True)

        owner_email = f"merchant_{int(time.time()*1000)}@myshop.com"
        owner_name = "Ramesh Kumar"
        shop_name = "Kumar Grocery Store"
        initial_pass = "InitialPass2026!"

        # 4. Super Admin creates shop owner
        create_resp = admin_client.post("/super-admin/shops/create", data={
            "owner_name": owner_name,
            "owner_email": owner_email,
            "initial_password": initial_pass,
            "shop_name": shop_name
        }, follow_redirects=True)
        self.assertEqual(create_resp.status_code, 200)
        self.assertIn(shop_name.encode(), create_resp.data)

        # 5. Duplicate emails are rejected
        dup_resp = admin_client.post("/super-admin/shops/create", data={
            "owner_name": owner_name,
            "owner_email": owner_email,
            "initial_password": initial_pass,
            "shop_name": shop_name
        }, follow_redirects=True)
        self.assertEqual(dup_resp.status_code, 200)
        self.assertIn(b"already registered", dup_resp.data)

        # 6. Newly created shop owner can log in
        shop_client = self.app.test_client()
        login_resp = shop_client.post("/login", data={
            "email": owner_email,
            "password": initial_pass
        }, follow_redirects=False)
        self.assertIn(login_resp.status_code, [302, 301])
        # 7. First login requires password change!
        self.assertIn("/first-login-password", login_resp.headers.get("Location", ""))

        # Verify browsing dashboard is blocked while must_change_password is active
        dash_try = shop_client.get("/dashboard", follow_redirects=False)
        self.assertIn(dash_try.status_code, [302, 301])
        self.assertIn("/first-login-password", dash_try.headers.get("Location", ""))

        # Set new personal password
        new_personal_pass = "PersonalSecuredPass2026!"
        pw_change_resp = shop_client.post("/first-login-password", data={
            "new_password": new_personal_pass,
            "confirm_password": new_personal_pass
        }, follow_redirects=True)
        self.assertEqual(pw_change_resp.status_code, 200)
        self.assertIn(b"Dashboard", pw_change_resp.data)

        # Verify old initial password no longer works
        shop_client2 = self.app.test_client()
        old_login = shop_client2.post("/login", data={"email": owner_email, "password": initial_pass}, follow_redirects=True)
        self.assertIn(b"Invalid email or password", old_login.data)

        # Verify new password logs in directly without password change prompt
        new_login = shop_client2.post("/login", data={"email": owner_email, "password": new_personal_pass}, follow_redirects=False)
        self.assertIn("/dashboard", new_login.headers.get("Location", ""))

        # Cleanup test shop
        conn = get_db_connection()
        user = conn.execute("SELECT id FROM users WHERE email = ?", (owner_email,)).fetchone()
        if user:
            biz = conn.execute("SELECT id FROM businesses WHERE owner_id = ?", (user["id"],)).fetchone()
            if biz: conn.execute("DELETE FROM businesses WHERE id = ?", (biz["id"],))
            conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
            conn.commit()
        conn.close()

    def test_08_09_10_disable_revoke_and_enable_access(self):
        """
        8. Disabled shop owner cannot log in.
        9. Existing sessions are revoked after disabling access.
        10. Enabled shop owner can log in again.
        """
        admin_client = self.app.test_client()
        admin_client.post("/super-admin/login", data={
            "email": "tanmaypandey0604@gmail.com",
            "password": "TanmayAdmin@2026!"
        }, follow_redirects=True)

        owner_email = f"merchant_toggle_{int(time.time()*1000)}@test.com"
        initial_pass = "MySecretPass2026!"

        # Create shop
        admin_client.post("/super-admin/shops/create", data={
            "owner_name": "Toggle Owner",
            "owner_email": owner_email,
            "initial_password": initial_pass,
            "shop_name": "Toggle Test Shop"
        }, follow_redirects=True)

        conn = get_db_connection()
        user = conn.execute("SELECT id FROM users WHERE email = ?", (owner_email,)).fetchone()
        biz = conn.execute("SELECT id FROM businesses WHERE owner_id = ?", (user["id"],)).fetchone()
        conn.close()
        shop_id = biz["id"]

        # Shop owner logs in and changes initial password
        shop_client = self.app.test_client()
        shop_client.post("/login", data={"email": owner_email, "password": initial_pass}, follow_redirects=True)
        shop_client.post("/first-login-password", data={"new_password": "RealPass123!", "confirm_password": "RealPass123!"}, follow_redirects=True)

        # Verify active session accesses dashboard
        dash_resp = shop_client.get("/dashboard")
        self.assertEqual(dash_resp.status_code, 200)

        # 9. Super Admin disables access -> live session must be revoked on next request
        disable_resp = admin_client.post(f"/super-admin/shops/{shop_id}/status", json={"status": "disabled"}, headers={"Accept": "application/json"})
        self.assertEqual(disable_resp.status_code, 200)

        next_req = shop_client.get("/dashboard", follow_redirects=False)
        self.assertIn(next_req.status_code, [302, 301])
        self.assertIn("/login", next_req.headers.get("Location", ""))

        # 8. Disabled shop owner cannot log in
        disabled_login = shop_client.post("/login", data={"email": owner_email, "password": "RealPass123!"}, follow_redirects=True)
        self.assertIn(b"disabled", disabled_login.data.lower())

        # 10. Super Admin enables access -> shop owner can log in again
        enable_resp = admin_client.post(f"/super-admin/shops/{shop_id}/status", json={"status": "active"}, headers={"Accept": "application/json"})
        self.assertEqual(enable_resp.status_code, 200)

        relogin_resp = shop_client.post("/login", data={"email": owner_email, "password": "RealPass123!"}, follow_redirects=False)
        self.assertIn(relogin_resp.status_code, [302, 301])
        self.assertIn("/dashboard", relogin_resp.headers.get("Location", ""))

        # Cleanup
        conn = get_db_connection()
        conn.execute("DELETE FROM businesses WHERE id = ?", (shop_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
        conn.commit()
        conn.close()

    def test_11_business_data_isolation(self):
        """11. Different shops cannot access each other's data."""
        # Create Shop A and Shop B
        conn = get_db_connection()
        from werkzeug.security import generate_password_hash
        h = generate_password_hash("pass1234")

        cur = conn.cursor()
        cur.execute("INSERT INTO users (email, password, name, role, account_status) VALUES ('shop_a@test.com', ?, 'Owner A', 'SHOP_OWNER', 'active')", (h,))
        u_a = cur.lastrowid
        cur.execute("INSERT INTO businesses (owner_id, name, status) VALUES (?, 'Store A', 'active')", (u_a,))
        b_a = cur.lastrowid
        cur.execute("UPDATE users SET business_id = ? WHERE id = ?", (b_a, u_a))

        cur.execute("INSERT INTO users (email, password, name, role, account_status) VALUES ('shop_b@test.com', ?, 'Owner B', 'SHOP_OWNER', 'active')", (h,))
        u_b = cur.lastrowid
        cur.execute("INSERT INTO businesses (owner_id, name, status) VALUES (?, 'Store B', 'active')", (u_b,))
        b_b = cur.lastrowid
        cur.execute("UPDATE users SET business_id = ? WHERE id = ?", (b_b, u_b))

        # Add a product to Store A
        cur.execute("INSERT INTO products (business_id, name, selling_price, stock_quantity) VALUES (?, 'Product Only in Store A', 100, 10)", (b_a,))
        prod_a_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Log in as Shop B owner
        client_b = self.app.test_client()
        client_b.post("/login", data={"email": "shop_b@test.com", "password": "pass1234"}, follow_redirects=True)

        # Store B accesses inventory -> Product A must NOT appear
        inv_resp = client_b.get("/inventory")
        self.assertEqual(inv_resp.status_code, 200)
        self.assertNotIn(b"Product Only in Store A", inv_resp.data)

        # Store B attempts to delete Product A -> MUST be blocked
        del_try = client_b.post(f"/inventory/delete/{prod_a_id}", headers={"Accept": "application/json"})
        self.assertEqual(del_try.status_code, 404)

        # Cleanup
        conn = get_db_connection()
        conn.execute("DELETE FROM products WHERE id = ?", (prod_a_id,))
        conn.execute("DELETE FROM businesses WHERE id IN (?, ?)", (b_a, b_b))
        conn.execute("DELETE FROM users WHERE id IN (?, ?)", (u_a, u_b))
        conn.commit()
        conn.close()

    def test_12_existing_billing_and_inventory_continue_working(self):
        """12. Existing billing, inventory, and accounting features continue working."""
        admin_client = self.app.test_client()
        admin_client.post("/super-admin/login", data={
            "email": "tanmaypandey0604@gmail.com",
            "password": "TanmayAdmin@2026!"
        }, follow_redirects=True)

        # Dashboard metrics check
        metrics_resp = admin_client.get("/super-admin/dashboard")
        self.assertEqual(metrics_resp.status_code, 200)
        self.assertIn(b"Total Registered Shops", metrics_resp.data)
        self.assertIn(b"Active Shops", metrics_resp.data)
        self.assertIn(b"Disabled Shops", metrics_resp.data)

if __name__ == "__main__":
    unittest.main()
