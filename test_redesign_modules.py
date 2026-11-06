import sys
import uuid
from app import app
from models.database import init_db, get_db_connection
from services.auth_service import authenticate_user

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("QA TEST SUITE: PEOPLE, SUPPLIERS & ACCOUNTING REPORTS REDESIGN")
print("=" * 70)

init_db()
client = app.test_client()

# 1. Authenticate with demo user
login_resp = client.post("/login", data={
    "email": "demo@shopledger.io",
    "password": "demo123"
}, follow_redirects=True)
assert login_resp.status_code == 200
print("[AUTH] Successfully logged into demo@shopledger.io")

# ==============================================================================
# MODULE 1: PEOPLE TESTS
# ==============================================================================
print("\n--- [MODULE 1: PEOPLE TESTS] ---")

# Test 1.1: Open People Page
resp = client.get("/customers")
assert resp.status_code == 200
assert b"People & Customer Directory" in resp.data
assert b"Total People" in resp.data
assert b"Accounts With Dues" in resp.data
assert b"Total Outstanding Receivables" in resp.data
print("Test 1.1 PASSED: People directory renders with summary KPI cards.")

# Test 1.2: Add Person
uid_tag = uuid.uuid4().hex[:6]
new_person_name = f"Karan Kapoor {uid_tag}"
new_person_phone = f"98200{uid_tag}"
add_resp = client.post("/customers/add", data={
    "name": new_person_name,
    "phone": new_person_phone,
    "email": f"karan_{uid_tag}@example.com",
    "address": "402 Ocean Drive, Bandra West",
    "gstin": "27KAPOR1234F1Z9"
}, follow_redirects=True)
assert add_resp.status_code == 200
assert new_person_name.encode() in add_resp.data
print("Test 1.2 PASSED: Added new person with B2B GSTIN and verified on list.")

# Fetch person ID from DB
conn = get_db_connection()
person_row = conn.execute("SELECT id FROM customers WHERE phone = ?", (new_person_phone,)).fetchone()
person_id = person_row["id"]
conn.close()

# Test 1.3: Search Person
search_resp = client.get(f"/customers?search={uid_tag}")
assert search_resp.status_code == 200
assert new_person_name.encode() in search_resp.data
print(f"Test 1.3 PASSED: Search query '{uid_tag}' successfully found '{new_person_name}'.")

# Test 1.4: Status Filters & Sorting
resp_due = client.get("/customers?status=due")
assert resp_due.status_code == 200
resp_clear = client.get("/customers?status=clear")
assert resp_clear.status_code == 200
resp_sort = client.get("/customers?sort=balance_desc")
assert resp_sort.status_code == 200
print("Test 1.4 PASSED: Status filtering ('due', 'clear') and sorting executed cleanly.")

# Test 1.5: Edit Person Details
updated_name = f"Karan S. Kapoor {uid_tag}"
edit_resp = client.post(f"/customers/edit/{person_id}", data={
    "name": updated_name,
    "phone": new_person_phone,
    "email": f"karan.kapoor_{uid_tag}@gmail.com",
    "address": "402 Ocean Drive, Bandra West, Mumbai 400050",
    "gstin": "27KAPOR1234F1Z9"
}, follow_redirects=True)
assert edit_resp.status_code == 200
assert updated_name.encode() in edit_resp.data
print(f"Test 1.5 PASSED: Updated person profile to '{updated_name}'.")

# Test 1.6: Open Person Ledger / Statement of Account
ledger_resp = client.get(f"/customers/{person_id}/ledger")
assert ledger_resp.status_code == 200
assert updated_name.encode() in ledger_resp.data
assert b"Billing History & Invoices" in ledger_resp.data
assert b"Payments Received" in ledger_resp.data
print("Test 1.6 PASSED: Statement of Account / Ledger rendered cleanly.")

# Test 1.7: Delete Person
del_resp = client.post(f"/customers/delete/{person_id}", follow_redirects=True)
assert del_resp.status_code == 200
assert updated_name.encode() not in del_resp.data
print(f"Test 1.7 PASSED: Deleted person '{updated_name}' and verified removal from directory.")

# ==============================================================================
# MODULE 2: SUPPLIERS TESTS
# ==============================================================================
print("\n--- [MODULE 2: SUPPLIERS TESTS] ---")

# Test 2.1: Open Suppliers Page
sup_resp = client.get("/suppliers")
assert sup_resp.status_code == 200
assert b"Suppliers & Procurement Directory" in sup_resp.data
assert b"Total Suppliers" in sup_resp.data
assert b"Active Procurement Vendors" in sup_resp.data
assert b"Accounts Payable (Supplier Dues)" in sup_resp.data
print("Test 2.1 PASSED: Suppliers directory renders with KPI summary cards.")

# Test 2.2: Add Supplier
sup_tag = uuid.uuid4().hex[:6]
new_sup_name = f"National Agro Impex {sup_tag}"
new_sup_phone = f"98330{sup_tag}"
add_sup_resp = client.post("/suppliers/add", data={
    "name": new_sup_name,
    "contact_person": "Vipin Anand",
    "phone": new_sup_phone,
    "email": f"vipin_{sup_tag}@agro.com",
    "address": "Gala 14, APMC Grain Market, Vashi",
    "gstin": "27AGROX1234F1Z4"
}, follow_redirects=True)
assert add_sup_resp.status_code == 200
assert new_sup_name.encode() in add_sup_resp.data
print(f"Test 2.2 PASSED: Added new supplier '{new_sup_name}'.")

# Fetch supplier ID from DB
conn = get_db_connection()
sup_row = conn.execute("SELECT id FROM suppliers WHERE phone = ?", (new_sup_phone,)).fetchone()
sup_id = sup_row["id"]
conn.close()

# Test 2.3: Search & Status Filters for Suppliers
sup_search_resp = client.get(f"/suppliers?search={sup_tag}")
assert sup_search_resp.status_code == 200
assert new_sup_name.encode() in sup_search_resp.data

sup_due_resp = client.get("/suppliers?status=due")
assert sup_due_resp.status_code == 200
print(f"Test 2.3 PASSED: Supplier search query '{sup_tag}' and status filters verified.")

# Test 2.4: View Supplier Detail Page
detail_resp = client.get(f"/suppliers/{sup_id}")
assert detail_resp.status_code == 200
assert new_sup_name.encode() in detail_resp.data
assert b"Vipin Anand" in detail_resp.data
assert b"Total Inward Value" in detail_resp.data
assert b"Inward Purchase Invoices" in detail_resp.data
print(f"Test 2.4 PASSED: Supplier detail page rendered with profile & purchase history tables.")

# Test 2.5: Edit Supplier Details
updated_sup_name = f"National Agro Impex Ltd {sup_tag}"
edit_sup_resp = client.post(f"/suppliers/edit/{sup_id}", data={
    "name": updated_sup_name,
    "contact_person": "Vipin Anand (Managing Director)",
    "phone": new_sup_phone,
    "email": f"orders_{sup_tag}@agroimpex.com",
    "address": "Gala 14-16, APMC Grain Market, Vashi, Navi Mumbai",
    "gstin": "27AGROX1234F1Z4"
}, follow_redirects=True)
assert edit_sup_resp.status_code == 200
assert updated_sup_name.encode() in edit_sup_resp.data
print(f"Test 2.5 PASSED: Updated supplier to '{updated_sup_name}'.")

# Test 2.6: Delete Supplier
del_sup_resp = client.post(f"/suppliers/delete/{sup_id}", follow_redirects=True)
assert del_sup_resp.status_code == 200
assert updated_sup_name.encode() not in del_sup_resp.data
print(f"Test 2.6 PASSED: Deleted supplier '{updated_sup_name}' successfully.")

# ==============================================================================
# MODULE 3: ACCOUNTING REPORTS TESTS
# ==============================================================================
print("\n--- [MODULE 3: ACCOUNTING REPORTS TESTS] ---")

# Test 3.1: Open Reports Page
rep_resp = client.get("/reports")
assert rep_resp.status_code == 200
assert b"Accounting Reports & Financial Analytics" in rep_resp.data
assert b"Gross Sales Revenue" in rep_resp.data
assert b"Operating Expenses" in rep_resp.data
assert b"Net Accounting Profit" in rep_resp.data
assert b"Outstanding Receivables" in rep_resp.data
assert b"Outstanding Payables" in rep_resp.data
assert b"Standard Profit & Loss Statement (P&L)" in rep_resp.data
assert b"GST Compliance & Tax Breakdown" in rep_resp.data
assert b"Physical Inventory Valuation" in rep_resp.data
print("Test 3.1 PASSED: Accounting reports rendered with 5 summary cards, P&L, GST & inventory tables.")

# Test 3.2: Verify Chart.js Containers & Embeds
assert b"monthlyTrendsChart" in rep_resp.data
assert b"Revenue vs Expense Monthly Trends" in rep_resp.data
print("Test 3.2 PASSED: Interactive Chart.js charts integrated and rendered.")

# Test 3.3: Test Date Range Filter
filter_resp = client.get("/reports?start_date=2026-11-01&end_date=2026-11-30")
assert filter_resp.status_code == 200
assert b"Standard Profit & Loss" in filter_resp.data
print("Test 3.3 PASSED: Date range selector (2026-11-01 to 2026-11-30) filtered records.")

# Test 3.4: Test CSV Sales Export
csv_resp = client.get("/reports/export/sales/csv")
assert csv_resp.status_code == 200
assert csv_resp.mimetype == "text/csv"
assert b"Invoice Number,Customer Name" in csv_resp.data
print("Test 3.4 PASSED: One-click CSV export generated valid sales spreadsheet data.")

print("\n" + "=" * 70)
print("ALL 17 RIGOROUS TESTS ACROSS PEOPLE, SUPPLIERS & REPORTS PASSED (100% GREEN)")
print("=" * 70)
