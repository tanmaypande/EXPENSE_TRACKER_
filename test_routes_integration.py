import sys
from app import app
from models.database import get_db_connection

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_routes():
    print("=" * 60)
    print("TESTING HTTP ROUTES INTEGRATION")
    print("=" * 60)

    client = app.test_client()

    conn = get_db_connection()
    user = conn.execute("SELECT u.id, u.email, u.name, u.business_id, b.name as biz_name FROM users u JOIN businesses b ON u.business_id = b.id LIMIT 1").fetchone()
    conn.close()

    if not user:
        print("[!] No user found for session testing.")
        return

    print(f"[*] Testing as user: {user['email']}, Business #{user['business_id']} ({user['biz_name']})")

    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["user_email"] = user["email"]
        sess["user_name"] = user["name"]
        sess["business_id"] = user["business_id"]
        sess["business_name"] = user["biz_name"]

    routes_to_test = [
        ("/pos", 200, "POS Billing Terminal"),
        ("/udhar", 200, "Udhar Management"),
        ("/notifications", 200, "Notification Center"),
        ("/invoices", 200, "Invoices List"),
        ("/reports", 200, "Accounting Reports"),
        ("/customers", 200, "People Module"),
    ]

    for path, expected_status, label in routes_to_test:
        res = client.get(path)
        assert res.status_code == expected_status, f"Route {path} failed: expected {expected_status}, got {res.status_code}"
        print(f" [PASS] {path} -> HTTP {res.status_code} ({label})")

    # Test Customer Ledger route if customer exists
    conn = get_db_connection()
    cust = conn.execute("SELECT id FROM customers WHERE business_id = ? LIMIT 1", (user["business_id"],)).fetchone()
    conn.close()
    if cust:
        res = client.get(f"/udhar/customer/{cust['id']}")
        assert res.status_code == 200, f"Customer ledger failed: {res.status_code}"
        print(f" [PASS] /udhar/customer/{cust['id']} -> HTTP 200 (Customer Udhar Ledger)")

    print("\n" + "=" * 60)
    print("ALL ROUTES VERIFIED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_routes()
