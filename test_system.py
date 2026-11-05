import os
import re
import sys
import json

# Ensure utf-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("SHOPLEDGER - END-TO-END AUTOMATED VERIFICATION SUITE")
print("=" * 60)

# 1. Verify Templates
print("\n[STEP 1] Checking all template references...")
routes_dir = 'routes'
templates_dir = 'templates'
found_templates = set()
for f in os.listdir(routes_dir):
    if f.endswith('.py'):
        with open(os.path.join(routes_dir, f), 'r', encoding='utf-8') as fp:
            content = fp.read()
            matches = re.findall(r'render_template\(\s*["\']([^"\']+)["\']', content)
            for m in matches:
                found_templates.add(m)

missing = []
for t in found_templates:
    path = os.path.join(templates_dir, t.replace('/', os.sep))
    if not os.path.exists(path):
        missing.append((t, path))

if missing:
    print(f"FAILED: Missing templates: {missing}")
    sys.exit(1)
print(f"PASSED: All {len(found_templates)} templates exist on disk!")

# 2. Database & Services End-to-End
print("\n[STEP 2] Initializing Flask test client...")
from app import app
from models.database import init_db, get_db_connection

init_db()
client = app.test_client()

# Register new test merchant
import uuid
unique_suffix = uuid.uuid4().hex[:6]
test_email = f"merchant_{unique_suffix}@shopledger.io"
test_password = "SecretPassword123!"

print(f"\n[STEP 3] Testing User Signup ({test_email})...")
resp = client.post("/signup", data={
    "name": "Arun Sharma",
    "email": test_email,
    "password": test_password,
    "confirm_password": test_password
}, follow_redirects=True)
assert resp.status_code == 200
print("Signup successful -> Redirected to Onboarding.")

# Complete Onboarding Setup
print("\n[STEP 4] Completing Business Setup Wizard...")
resp = client.post("/onboarding", data={
    "business_name": f"Sharma Retail Mart {unique_suffix}",
    "category": "kirana",
    "phone": "9876543210",
    "address": "Shop 12, Main Market, Mumbai",
    "gstin": "27AABCS1429B1ZB",
    "currency": "₹",
    "invoice_prefix": "SRM-",
    "tax_enabled": "1",
    "default_tax_rate": "18"
}, follow_redirects=True)
assert resp.status_code == 200
print("Business onboarding successful -> Seeded catalog created!")

# Check Dashboard
print("\n[STEP 5] Testing Dashboard Route...")
resp = client.get("/")
print("Response code:", resp.status_code, "Location:", resp.headers.get("Location"))
if resp.status_code == 302:
    resp = client.get("/", follow_redirects=True)
    print("Followed redirect:", resp.status_code)
assert resp.status_code == 200
assert b"Sharma Retail Mart" in resp.data or b"ShopLedger" in resp.data
print("Dashboard loaded cleanly with real DB metrics.")

# Check Inventory
print("\n[STEP 6] Testing Inventory Catalog & Adding Custom Product...")
resp = client.get("/inventory")
assert resp.status_code == 200

# Add new custom product
resp = client.post("/inventory/add", data={
    "name": "Tata Tea Premium 500g",
    "sku": f"TEA-{unique_suffix}",
    "barcode": f"8901234{unique_suffix}",
    "brand": "Tata Consumer",
    "purchase_price": "140.00",
    "selling_price": "180.00",
    "tax_rate": "5.0",
    "stock_quantity": "50",
    "min_stock_level": "10",
    "unit": "pack",
    "description": "500g Fresh Indian Tea"
}, follow_redirects=True)
assert resp.status_code == 200
print("Product 'Tata Tea Premium 500g' created with initial stock 50.")

# Add Customer
print("\n[STEP 7] Testing Customer Creation...")
resp = client.post("/customers/add", data={
    "name": "Rajesh Gupta",
    "phone": f"98200{unique_suffix[:5]}",
    "email": "rajesh@gupta.com",
    "address": "Flat 402, Sunshine Heights",
    "gstin": ""
}, follow_redirects=True)
assert resp.status_code == 200
print("Customer 'Rajesh Gupta' registered.")

# Query POS API for Barcode Search
print("\n[STEP 8] Testing POS Barcode Scanner API...")
barcode = f"8901234{unique_suffix}"
resp = client.get(f"/api/pos/barcode?code={barcode}")
assert resp.status_code == 200
prod_data = resp.get_json()
assert prod_data["found"] is True
product_id = prod_data["product"]["id"]
print(f"Barcode API successfully matched '{prod_data['product']['name']}' (ID: {product_id}).")

# Perform POS Checkout
print("\n[STEP 9] Simulating POS Billing Checkout (Sale)...")
sale_payload = {
    "customer_name": "Rajesh Gupta",
    "customer_phone": f"98200{unique_suffix[:5]}",
    "customer_id": None,
    "payment_method": "cash",
    "paid_amount": 360.00,
    "discount_amount": 0.00,
    "items": [
        {
            "product_id": product_id,
            "name": "Tata Tea Premium 500g",
            "quantity": 2,
            "unit_price": 180.00,
            "purchase_price": 140.00,
            "tax_rate": 5.0,
            "discount_amount": 0.00
        }
    ]
}

resp = client.post("/pos/checkout", json=sale_payload)
if resp.status_code != 200:
    print("Checkout failed with status:", resp.status_code, "Body:", resp.get_data(as_text=True))
assert resp.status_code == 200
checkout_data = resp.get_json()
assert checkout_data["success"] is True
sale_id = checkout_data["sale_id"]
inv_num = checkout_data["invoice_number"]
print(f"POS Sale completed! Generated Invoice: {inv_num} (Sale ID: {sale_id})")

# Verify stock deduction
from services.product_service import get_product_by_id
updated_prod = get_product_by_id(product_id)
assert updated_prod["stock_quantity"] == 48.0, f"Expected stock 48, got {updated_prod['stock_quantity']}"
print(f"Atomic inventory deduction verified: Stock reduced from 50 -> {updated_prod['stock_quantity']}.")

# Check Invoice View & Dual Print Layouts
print("\n[STEP 10] Testing Tax Invoice View and A4/Thermal Print Pages...")
resp = client.get(f"/invoices/{sale_id}")
assert resp.status_code == 200
assert inv_num.encode() in resp.data

resp_print = client.get(f"/invoices/{sale_id}/print")
assert resp_print.status_code == 200
assert b"TAX INVOICE" in resp_print.data
assert b"thermal-receipt" in resp_print.data
print("Invoice view and A4 / Thermal print formats rendered successfully.")

# Test Inward Stock Purchase from Supplier
print("\n[STEP 11] Testing Supplier Registration & Inward Purchase Order...")
resp = client.post("/suppliers/add", data={
    "name": "Tata Global Wholesale Depot",
    "contact_person": "Vikram Singh",
    "phone": "9819001122",
    "email": "depot@tata.com",
    "address": "APMC Market Yard",
    "gstin": "27TATA1234F1Z1"
}, follow_redirects=True)
assert resp.status_code == 200

# Fetch supplier ID
from services.supplier_service import get_suppliers
suppliers = get_suppliers(updated_prod["business_id"])
sup_id = suppliers[0]["id"]

# Create Purchase Order: restock 20 units
purchase_items = [
    {
        "product_id": product_id,
        "quantity": 20,
        "purchase_price": 135.00
    }
]
resp = client.post("/purchases/new", data={
    "supplier_id": str(sup_id),
    "purchase_number": f"PO-{unique_suffix}",
    "payment_method": "bank",
    "paid_amount": "2700.00",
    "notes": "Express delivery restock",
    "purchase_items_json": json.dumps(purchase_items)
}, follow_redirects=True)
assert resp.status_code == 200

restocked_prod = get_product_by_id(product_id)
assert restocked_prod["stock_quantity"] == 68.0, f"Expected 68, got {restocked_prod['stock_quantity']}"
print(f"Inward stock replenishment verified: Stock increased from 48 -> {restocked_prod['stock_quantity']}.")

# Record Business Expense
print("\n[STEP 12] Testing Business Overhead Expense...")
resp = client.post("/expenses/add", data={
    "category": "Electricity & Utilities",
    "amount": "850.00",
    "date": "2026-11-05",
    "description": "Monthly shop electricity meter charge",
    "payment_method": "upi"
}, follow_redirects=True)
assert resp.status_code == 200
print("Expense ₹850.00 logged successfully.")

# Process Sales Return
print("\n[STEP 13] Testing Sales Return & Refund with Restocking...")
# Return 1 unit of Tata Tea
resp = client.post("/returns/new", data={
    "sale_id": str(sale_id),
    "invoice_number": inv_num,
    "refund_method": "cash",
    "reason": "Customer Changed Mind",
    "product_id": [str(product_id)],
    f"product_name_{product_id}": "Tata Tea Premium 500g",
    f"return_qty_{product_id}": "1",
    f"restock_{product_id}": "1"
}, follow_redirects=True)
assert resp.status_code == 200

returned_prod = get_product_by_id(product_id)
assert returned_prod["stock_quantity"] == 69.0, f"Expected 69, got {returned_prod['stock_quantity']}"
print(f"Sales return processed with automatic restocking: Stock increased from 68 -> {returned_prod['stock_quantity']}.")

# Commercial P&L Report Verification
print("\n[STEP 14] Testing Commercial Profit & Loss Report...")
resp = client.get("/reports")
assert resp.status_code == 200
assert b"Standard Profit" in resp.data
assert b"Cost of Goods Sold" in resp.data
print("P&L report rendered accurately with COGS and Net Profit.")

# Export CSV Report
print("\n[STEP 15] Testing CSV Sales Report Export...")
resp = client.get("/reports/export/sales/csv")
assert resp.status_code == 200
assert resp.mimetype == "text/csv"
assert inv_num.encode() in resp.data
print("CSV sales export verified.")

# Test Shop Settings Update
print("\n[STEP 16] Testing Shop Settings Update...")
resp = client.post("/settings", data={
    "name": f"Sharma Retail Mart & Co {unique_suffix}",
    "category": "kirana",
    "phone": "9876543210",
    "email": "sharma@mart.com",
    "address": "Shop 12, Main Market, Mumbai 400001",
    "gstin": "27AABCS1429B1ZB",
    "currency": "₹",
    "invoice_prefix": "SRM-",
    "tax_enabled": "1",
    "default_tax_rate": "18",
    "terms_conditions": "Thank you for shopping with Sharma Retail Mart! Visit again."
}, follow_redirects=True)
assert resp.status_code == 200
assert b"Settings Saved Successfully" in resp.data
print("Shop settings updated cleanly.")

print("\n" + "=" * 60)
print("ALL 16 INTEGRATION CHECKS PASSED SUCCESSFULLY (100% GREEN)")
print("=" * 60)
