from models.database import get_db_connection

def get_business_by_id(business_id):
    if not business_id:
        return None
    conn = get_db_connection()
    biz = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
    conn.close()
    return dict(biz) if biz else None

def get_business_by_owner(owner_id):
    conn = get_db_connection()
    biz = conn.execute("SELECT * FROM businesses WHERE owner_id = ? ORDER BY id ASC LIMIT 1", (owner_id,)).fetchone()
    conn.close()
    return dict(biz) if biz else None

def create_business(owner_id, name, category="retail", phone="", email="", address="", gstin="", currency="₹", invoice_prefix="INV-", tax_enabled=1, default_tax_rate=0.0, terms_conditions=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO businesses 
    (owner_id, name, category, phone, email, address, gstin, currency, invoice_prefix, tax_enabled, default_tax_rate, terms_conditions)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        owner_id, name.strip(), category, phone.strip(), email.strip(), 
        address.strip(), gstin.strip().upper(), currency.strip() or "₹", 
        invoice_prefix.strip() or "INV-", 1 if tax_enabled else 0, 
        float(default_tax_rate or 0.0),
        terms_conditions or "Thank you for shopping with us! Please retain this invoice for your records."
    ))
    conn.commit()
    biz_id = cur.lastrowid
    
    # Update owner's active business_id
    cur.execute("UPDATE users SET business_id = ? WHERE id = ?", (biz_id, owner_id))
    conn.commit()
    conn.close()

    # Seed starter categories and products according to business type
    seed_starter_catalog(biz_id, category)
    return biz_id

def update_business(business_id, name, category, phone, email, address, gstin, currency, invoice_prefix, tax_enabled, default_tax_rate, terms_conditions):
    conn = get_db_connection()
    conn.execute("""
    UPDATE businesses
    SET name = ?, category = ?, phone = ?, email = ?, address = ?, gstin = ?,
        currency = ?, invoice_prefix = ?, tax_enabled = ?, default_tax_rate = ?, terms_conditions = ?
    WHERE id = ?
    """, (
        name.strip(), category, phone.strip(), email.strip(), address.strip(),
        gstin.strip().upper(), currency.strip() or "₹", invoice_prefix.strip() or "INV-",
        1 if tax_enabled else 0, float(default_tax_rate or 0.0), terms_conditions, business_id
    ))
    conn.commit()
    conn.close()

def seed_starter_catalog(business_id, category):
    """Provides realistic starter inventory so a new shopkeeper can test and bill immediately."""
    conn = get_db_connection()
    cur = conn.cursor()

    starter_items = {
        "kirana": [
            ("Packaged Staples", [
                ("Aashirvaad Shudh Chakki Atta 5kg", "ATTA-5KG", "890103000001", 240.0, 275.0, 0.0, 25.0, 5.0, "packet"),
                ("Fortune Sunlite Sunflower Oil 1L", "OIL-1L", "890103000002", 125.0, 145.0, 5.0, 30.0, 6.0, "packet"),
                ("Tata Salt Vacuum Evaporated 1kg", "SALT-1KG", "890103000003", 22.0, 28.0, 0.0, 50.0, 10.0, "packet"),
                ("Madhur Pure & Hygienic Sugar 1kg", "SUGAR-1KG", "890103000004", 42.0, 48.0, 5.0, 40.0, 8.0, "packet"),
                ("Tata Sampann Toor Dal 1kg", "DAL-1KG", "890103000005", 145.0, 170.0, 0.0, 20.0, 4.0, "packet")
            ]),
            ("Dairy & Bakery", [
                ("Amul Taaza Homogenised Milk 1L", "MILK-1L", "890103000006", 64.0, 72.0, 0.0, 20.0, 5.0, "packet"),
                ("Amul Salted Butter 100g", "BUTTER-100G", "890103000007", 50.0, 58.0, 12.0, 35.0, 6.0, "box"),
                ("Britannia Brown Bread 400g", "BREAD-400G", "890103000008", 40.0, 50.0, 0.0, 15.0, 3.0, "packet")
            ]),
            ("Snacks & Beverages", [
                ("Parle-G Gold Biscuits 1kg", "PARLE-G-1KG", "890103000009", 110.0, 130.0, 18.0, 30.0, 5.0, "packet"),
                ("Maggi 2-Minute Noodles 280g", "MAGGI-280G", "890103000010", 45.0, 56.0, 18.0, 40.0, 10.0, "packet"),
                ("Tata Tea Gold Pouch 250g", "TEA-250G", "890103000011", 130.0, 155.0, 5.0, 25.0, 5.0, "packet")
            ])
        ],
        "clothing": [
            ("Menswear", [
                ("Men's Formal Oxford Shirt Blue", "SHIRT-M-BLU", "890201000001", 650.0, 1199.0, 5.0, 15.0, 3.0, "pcs"),
                ("Men's Slim Fit Denim Jeans 32", "JEANS-M-32", "890201000002", 750.0, 1499.0, 12.0, 20.0, 4.0, "pcs"),
                ("Men's Pure Cotton Crew T-Shirt Black", "TSHIRT-M-BLK", "890201000003", 280.0, 599.0, 5.0, 30.0, 5.0, "pcs")
            ]),
            ("Womenswear", [
                ("Women's Cotton Floral Kurti M", "KURTI-W-M", "890201000004", 450.0, 899.0, 5.0, 18.0, 3.0, "pcs"),
                ("Women's Stretchable Leggings Navy", "LEG-W-NVY", "890201000005", 220.0, 449.0, 5.0, 25.0, 5.0, "pcs")
            ])
        ],
        "electronics": [
            ("Accessories & Audio", [
                ("Fast Charging USB-C Braided Cable 1.5m", "CABLE-TYPEC", "890301000001", 120.0, 299.0, 18.0, 40.0, 8.0, "pcs"),
                ("65W GaN Fast Charger Adapter", "CHARGER-65W", "890301000002", 750.0, 1499.0, 18.0, 15.0, 3.0, "pcs"),
                ("Wireless Bluetooth Earbuds with ANC", "EARBUDS-BT", "890301000003", 1100.0, 2299.0, 18.0, 12.0, 2.0, "pcs")
            ])
        ]
    }

    # Default to kirana if not matched
    cat_key = category if category in starter_items else "kirana"
    groups = starter_items[cat_key]

    for cat_name, items in groups:
        cur.execute("INSERT INTO categories (business_id, name) VALUES (?, ?)", (business_id, cat_name))
        cat_id = cur.lastrowid
        for name, sku, barcode, cost, mrp, tax, qty, min_qty, unit in items:
            cur.execute("""
            INSERT INTO products 
            (business_id, name, sku, barcode, category_id, purchase_price, selling_price, tax_rate, stock_quantity, min_stock_level, unit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (business_id, name, sku, barcode, cat_id, cost, mrp, tax, qty, min_qty, unit))
            prod_id = cur.lastrowid
            # Log initial stock movement
            cur.execute("""
            INSERT INTO stock_movements (business_id, product_id, change_qty, new_stock, reason, notes)
            VALUES (?, ?, ?, ?, 'initial', 'Initial inventory setup')
            """, (business_id, prod_id, qty, qty))

    conn.commit()
    conn.close()
