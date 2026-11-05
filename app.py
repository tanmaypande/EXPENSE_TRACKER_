import os
import sys
import json
import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = Flask(__name__)
app.secret_key = "my_secret_key_123"

# ---------------- DATABASE CONNECTION ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "expense.db")

def get_db_connection():
    print("[DB] USING DATABASE:", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        type TEXT DEFAULT 'expense',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)
    # Ensure 'type' column exists if db was created with legacy schema
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(record)")
    columns = [row["name"] for row in cur.fetchall()]
    if "type" not in columns:
        try:
            conn.execute("ALTER TABLE record ADD COLUMN type TEXT DEFAULT 'expense'")
            conn.commit()
        except Exception as e:
            print("[DB] Column migration notice:", e)
    conn.commit()
    conn.close()

# Auto-initialize DB schema on launch
init_db()


# ---------------- ROOT ROUTE ----------------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/dashboard")
    return redirect("/login")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session and request.method == "GET":
        return redirect("/dashboard")

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            return redirect("/dashboard")
        else:
            error = "Invalid email or password. Please try again."

    return render_template("login.html", error=error)


# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    print("[ROUTE] SIGNUP ROUTE HIT")
    if "user_id" in session and request.method == "GET":
        return redirect("/dashboard")

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            error = "Email and password are required."
            return render_template("signup.html", error=error)

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, hashed_password)
            )
            conn.commit()
            
            # Fetch the newly registered user to automatically sign them in
            new_user = conn.execute("SELECT id, email FROM users WHERE email = ?", (email,)).fetchone()
            conn.close()
            
            if new_user:
                session["user_id"] = new_user["id"]
                session["user_email"] = new_user["email"]
                return redirect("/dashboard")
            return redirect("/login")

        except sqlite3.IntegrityError:
            error = "This email address is already registered."

    return render_template("signup.html", error=error)


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    user_id = session["user_id"]

    # Retrieve user email if not in session
    user_email = session.get("user_email")
    if not user_email:
        user_row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
        user_email = user_row["email"] if user_row else "user@fintech.local"
        session["user_email"] = user_email

    # Retrieve all records (ordered newest first)
    records_rows = conn.execute(
        "SELECT id, date, category, amount, description, COALESCE(type, 'expense') AS type FROM record WHERE user_id = ? ORDER BY date DESC, id DESC",
        (user_id,)
    ).fetchall()

    records = [dict(row) for row in records_rows]

    # Calculate actual totals
    total_income_row = conn.execute(
        "SELECT SUM(amount) FROM record WHERE user_id = ? AND type = 'income'",
        (user_id,)
    ).fetchone()
    total_income = float(total_income_row[0] or 0)

    total_expense_row = conn.execute(
        "SELECT SUM(amount) FROM record WHERE user_id = ? AND (type = 'expense' OR type IS NULL)",
        (user_id,)
    ).fetchone()
    total_expense = float(total_expense_row[0] or 0)

    total_balance = total_income - total_expense
    savings = max(0.0, total_balance)
    savings_rate = round((savings / total_income) * 100, 1) if total_income > 0 else 0

    # Aggregate category distribution for expenses (real data)
    cat_rows = conn.execute(
        """
        SELECT category, SUM(amount) AS total
        FROM record
        WHERE user_id = ? AND (type = 'expense' OR type IS NULL)
        GROUP BY category
        ORDER BY total DESC
        """,
        (user_id,)
    ).fetchall()

    categories_data = [{"category": row["category"], "total": float(row["total"])} for row in cat_rows]

    # Aggregate timeline / monthly trend (real data)
    monthly_rows = conn.execute(
        """
        SELECT 
            strftime('%Y-%m', date) AS month,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN type = 'expense' OR type IS NULL THEN amount ELSE 0 END) AS expense
        FROM record
        WHERE user_id = ?
        GROUP BY month
        ORDER BY month ASC
        LIMIT 12
        """,
        (user_id,)
    ).fetchall()

    monthly_data = [
        {"month": row["month"], "income": float(row["income"]), "expense": float(row["expense"])}
        for row in monthly_rows
    ]

    conn.close()

    # Fallback legacy variable names preserved so old template references never fail
    return render_template(
        "dashboard.html",
        expenses=records,
        records=records,
        total=total_expense,
        income=total_income,
        total_income=total_income,
        total_expense=total_expense,
        balance=total_balance,
        savings=savings,
        savings_rate=savings_rate,
        user_email=user_email,
        categories_json=json.dumps(categories_data),
        monthly_json=json.dumps(monthly_data)
    )


# ---------------- ADD TRANSACTION ----------------
# Dedicated page GET
@app.route("/add", methods=["GET"])
def add_expense_page():
    if "user_id" not in session:
        return redirect("/login")
    trans_type = request.args.get("type", "expense").lower()
    return render_template("add_expense.html", initial_type=trans_type, user_email=session.get("user_email", ""))


# Handle Form Submit POST (Supports both expense and income seamlessly)
@app.route("/add", methods=["POST"])
def add_expense():
    if "user_id" not in session:
        return redirect("/login")

    date = request.form.get("date", "").strip()
    category = request.form.get("category", "").strip() or "General"
    raw_amount = request.form.get("amount", "0")
    try:
        amount = float(raw_amount)
    except ValueError:
        amount = 0.0

    description = request.form.get("description", "").strip()
    trans_type = request.form.get("type", "expense").strip().lower()
    if trans_type not in ["expense", "income"]:
        trans_type = "expense"

    user_id = session["user_id"]

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO record (user_id, date, category, amount, description, type)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, date, category, amount, description, trans_type)
    )
    conn.commit()
    conn.close()

    return redirect("/dashboard")


# ---------------- EDIT TRANSACTION ----------------
@app.route("/edit/<int:id>", methods=["POST"])
def edit_expense(id):
    if "user_id" not in session:
        return redirect("/login")

    date = request.form.get("date", "").strip()
    category = request.form.get("category", "").strip() or "General"
    raw_amount = request.form.get("amount", "0")
    try:
        amount = float(raw_amount)
    except ValueError:
        amount = 0.0

    description = request.form.get("description", "").strip()
    trans_type = request.form.get("type", "expense").strip().lower()
    if trans_type not in ["expense", "income"]:
        trans_type = "expense"

    conn = get_db_connection()
    conn.execute(
        """
        UPDATE record 
        SET date = ?, category = ?, amount = ?, description = ?, type = ?
        WHERE id = ? AND user_id = ?
        """,
        (date, category, amount, description, trans_type, id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect("/dashboard")


# ---------------- DELETE TRANSACTION ----------------
@app.route("/delete/<int:id>", methods=["GET", "POST"])
def delete_expense(id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM record WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect("/dashboard")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)
