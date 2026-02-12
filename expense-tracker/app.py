from flask import Flask, render_template, request, redirect, session, url_for
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "my_secret_key_123"   # REQUIRED for sessions


# ---------------- DATABASE CONNECTION ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "expense.db")

def get_db_connection():
    print(" USING DATABASE:", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- LOGIN ----------------
@app.route("/")
def home():
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower()
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect("/dashboard")
        else:
            return "Invalid email or password"

    return render_template("login.html")  



# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    print("👉 SIGNUP ROUTE HIT")
    if request.method == "POST":
        email = request.form["email"].lower()
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, hashed_password)
            )
            conn.commit()
            conn.close()
            return redirect("/login")

        except sqlite3.IntegrityError:
            return "Email already registered"

    return render_template("signup.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    expenses = conn.execute(
        "SELECT date, category, amount FROM record WHERE user_id = ?",
        (session["user_id"],)
    ).fetchall()

    total = conn.execute(
        "SELECT SUM(amount) FROM record WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()[0] or 0

    income = 0  

    conn.close()

    return render_template(
        "dashboard.html",
        expenses=expenses,
        total=total,
        income=income
    )


# ---------------- ADD EXPENSE ----------------
@app.route("/add", methods=["GET"])
def add_expense_page():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("add_expense.html")


# ---------------- HANDLE ADD EXPENSE FORM SUBMIT ----------------
@app.route("/add", methods=["POST"])
def add_expense():
    if "user_id" not in session:
        return redirect("/login")

    date = request.form["date"]
    category = request.form["category"]
    amount = float(request.form["amount"])
    description = request.form["description"]
    user_id = session["user_id"]

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO record (user_id, date, category, amount, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, date, category, amount, description)
    )
    conn.commit()
    conn.close()

    return redirect("/dashboard")



# ---------------- DELETE EXPENSE ----------------
@app.route("/delete/<int:id>")
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
