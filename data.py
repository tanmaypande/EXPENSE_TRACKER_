import sqlite3
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Connect to database (creates expense.db if not exists)
connection = sqlite3.connect("expense.db")
cursor = connection.cursor()

# ---------------- USERS TABLE ----------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY AUTOINCREMENT,
email TEXT UNIQUE NOT NULL,
password TEXT NOT NULL
)
""")

# ---------------- EXPENSE RECORD TABLE ----------------
cursor.execute("""
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

connection.commit()
connection.close()

print("[SUCCESS] Database setup completed successfully!")
