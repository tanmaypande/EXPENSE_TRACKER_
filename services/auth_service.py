from werkzeug.security import generate_password_hash, check_password_hash
from models.database import get_db_connection

def register_user(email, password, name=None, role="owner"):
    email = email.strip().lower()
    hashed = generate_password_hash(password)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)",
        (email, hashed, name or email.split("@")[0].capitalize(), role)
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id

def authenticate_user(email, password):
    email = email.strip().lower()
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if user and check_password_hash(user["password"], password):
        return dict(user)
    return None

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def update_user_business(user_id, business_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET business_id = ? WHERE id = ?", (business_id, user_id))
    conn.commit()
    conn.close()
