import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, request, send_file

# =============================
# APP SETUP
# =============================

print(">>> APP.PY LOADED <<<")

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
DATABASE = BASE_DIR / "invoices.db"

FREE_LIMIT = 3

# =============================
# DATABASE HELPERS
# =============================

def get_db():
    return sqlite3.connect(DATABASE)

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT,
            amount REAL,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    c.execute("""
        INSERT OR IGNORE INTO settings (key, value)
        VALUES ('is_paid', '0')
    """)

    conn.commit()
    conn.close()

def is_paid():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='is_paid'")
    row = c.fetchone()
    conn.close()
    return row and row[0] == "1"

def set_paid(value: bool):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('is_paid', ?)",
        ("1" if value else "0",)
    )
    conn.commit()
    conn.close()

def invoice_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM invoices")
    count = c.fetchone()[0]
    conn.close()
    return count

# =============================
# ROUTES
# =============================

@app.route("/")
def home():
    paid = is_paid()
    count = invoice_count()

    status = "🟢 PRO (Unlimited)" if paid else f"🔒 FREE ({count}/{FREE_LIMIT})"

    return f"""
    <h1>Invoice App</h1>
    <p>Status: <b>{status}</b></p>

    <form method="POST" action="/create">
        <input name="customer" placeholder="Customer name" required>
        <input name="amount" placeholder="Amount" required>
        <button>Create Invoice</button>
    </form>

    <p><a href="/_test-pay">Simulate Payment</a></p>
    """

@app.route("/create", methods=["POST"])
def create_invoice():
    if not is_paid() and invoice_count() >= FREE_LIMIT:
        return "<h2>Free limit reached ❌</h2>"

    customer = request.form["customer"]
    amount = request.form["amount"]

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO invoices (customer, amount, created_at) VALUES (?, ?, ?)",
        (customer, amount, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    return "<h2>Invoice created ✅</h2><a href='/'>Back</a>"

@app.route("/_test-pay")
def test_pay():
    set_paid(True)
    return """
    <h2>Payment simulated ✅</h2>
    <p>Restart or redeploy the app — payment should persist.</p>
    <a href="/">Back</a>
    """

@app.route("/_proof")
def proof():
    return "<h1>Routing works ✅</h1>"

# =============================
# STARTUP
# =============================

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)