import os
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, send_file
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import stripe
import psycopg2
from psycopg2.extras import RealDictCursor

print(">>> APP.PY LOADED <<<")

# -------------------------------------------------
# App + Config
# -------------------------------------------------

app = Flask(__name__)

BASE_URL = os.environ.get("BASE_URL", "http://localhost:10000")
DATABASE_URL = os.environ.get("DATABASE_URL")

print("BASE_URL =", BASE_URL)
print("USING POSTGRES =", bool(DATABASE_URL))

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

# -------------------------------------------------
# Database helpers
# -------------------------------------------------

def get_db():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode="require")
    return sqlite3.connect("invoices.db")

def init_db():
    conn = get_db()
    cur = conn.cursor()

    if DATABASE_URL:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

    cur.execute("""
        INSERT INTO settings (key, value)
        VALUES ('is_paid', '0')
        ON CONFLICT (key) DO NOTHING
    """)

    conn.commit()
    conn.close()

init_db()

def is_paid():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='is_paid'")
    row = cur.fetchone()
    conn.close()
    return row and row[0] == "1"

def set_paid():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE settings SET value='1' WHERE key='is_paid'"
    )
    conn.commit()
    conn.close()

# -------------------------------------------------
# Routes
# -------------------------------------------------

@app.route("/")
def home():
    paid = is_paid()
    return f"""
    <h1>Invoice App</h1>
    <p>Status: {"PAID ✅" if paid else "FREE ❌"}</p>
    <a href="/upgrade">Upgrade</a>
    """

@app.route("/upgrade")
def upgrade():
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{
            "price": STRIPE_PRICE_ID,
            "quantity": 1
        }],
        success_url=f"{BASE_URL}/success",
        cancel_url=f"{BASE_URL}/"
    )
    return redirect(session.url)

@app.route("/success")
def success():
    set_paid()
    return """
    <h2>Payment Successful 🎉</h2>
    <p>Your account is now upgraded.</p>
    <a href="/">Return Home</a>
    """

@app.route("/health")
def health():
    return "ok", 200

# -------------------------------------------------
# Run
# -------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
