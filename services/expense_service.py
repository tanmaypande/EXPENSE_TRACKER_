from models.database import get_db_connection

BUSINESS_EXPENSE_CATEGORIES = [
    "Rent",
    "Employee Salaries",
    "Electricity & Power",
    "Water & Sanitation",
    "Internet & Telephone",
    "Transportation & Fuel",
    "Packaging Materials",
    "Store Maintenance & Repairs",
    "Marketing & Promotion",
    "Taxes & License Fees",
    "Office Stationery",
    "Miscellaneous"
]

def get_expenses(business_id, category=None, start_date=None, end_date=None, limit=100):
    conn = get_db_connection()
    query = "SELECT * FROM expenses WHERE business_id = ?"
    params = [business_id]

    if category and category != "all":
        query += " AND category = ?"
        params.append(category)

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " ORDER BY date DESC, id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_expense(business_id, category, amount, date, description="", payment_method="cash"):
    amt = float(amount or 0.0)
    if amt <= 0:
        raise ValueError("Expense amount must be greater than zero.")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO expenses (business_id, category, amount, date, description, payment_method)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (business_id, category.strip(), amt, date, description.strip(), payment_method))
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid

def delete_expense(expense_id, business_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM expenses WHERE id = ? AND business_id = ?", (expense_id, business_id))
    conn.commit()
    conn.close()

def get_expense_categories():
    return BUSINESS_EXPENSE_CATEGORIES
