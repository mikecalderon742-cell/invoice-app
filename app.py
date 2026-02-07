import os
import sqlite3
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from flask import Flask, request, redirect, send_file
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import stripe

print(">>> APP.PY LOADED <<<")

# ---------------- CONFIG ----------------

BASE_URL = os.environ.get("BASE_URL", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

FREE_INVOICE_LIMIT = 3
SQLITE_DB = "invoices.db"

print("BASE_URL =", BASE_URL)

stripe.api_key = STRIPE_SECRET_KEY

app = Flask(__name__)

# ---------------- DATABASE (STEP 2 ONLY) ----------------

def get_db():
    """
    STEP 2:
    - If DATABASE_URL exists → Postgres
    - Else → SQLite (current behavior)
    """
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return sqlite3.connect(SQLITE_DB)

def init_db():
    conn = get_db()
    c = conn.cursor()

    if DATABASE_URL:
        c.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id SERIAL PRIMARY KEY,
                client TEXT,
                item TEXT,
                amount REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        c.execute("""
            INSERT INTO settings (key, value)
            VALUES ('is_paid', '0')
            ON CONFLICT (key) DO NOTHING
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client TEXT,
                item TEXT,
                amount REAL
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

init_db()

# ---------------- HELPERS ----------------

def is_paid():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='is_paid'")
    row = c.fetchone()
    conn.close()
    return row and (row["value"] if DATABASE_URL else row[0]) == "1"

def invoice_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM invoices")
    count = c.fetchone()
    conn.close()
    return count["count"] if DATABASE_URL else count[0]

def format_invoice_number(invoice_id):
    return f"{datetime.now().year}-INV-{str(invoice_id).zfill(4)}"

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    count = invoice_count()
    paid = is_paid()

    remaining = "Unlimited" if paid else max(0, FREE_INVOICE_LIMIT - count)
    status = "Pro (Unlimited)" if paid else f"Free ({remaining} left)"

    upgrade_link = ""
    if not paid:
        upgrade_link = "<p><a href='/upgrade'>Upgrade to Pro</a></p>"

    return f"""
    <h2>Invoice App is LIVE</h2>
    <p>Status: {status}</p>

    <form method="post" action="/create">
        Client <input name="client" required><br>
        Item <input name="item" required><br>
        Amount <input name="amount" required><br>
        <button>Create Invoice</button>
    </form>

    {upgrade_link}

    <p><a href="/invoices">View invoices</a></p>
    """

@app.route("/create", methods=["POST"])
def create():
    if not is_paid() and invoice_count() >= FREE_INVOICE_LIMIT:
        return redirect("/upgrade")

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO invoices (client, item, amount) VALUES (%s, %s, %s)"
        if DATABASE_URL else
        "INSERT INTO invoices (client, item, amount) VALUES (?, ?, ?)",
        (request.form["client"], request.form["item"], request.form["amount"])
    )
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/invoices")
def invoices():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, client, item, amount FROM invoices")
    rows = c.fetchall()
    conn.close()

    html = "<h2>Invoices</h2>"
    for r in rows:
        rid = r["id"] if DATABASE_URL else r[0]
        client = r["client"] if DATABASE_URL else r[1]
        item = r["item"] if DATABASE_URL else r[2]
        amount = r["amount"] if DATABASE_URL else r[3]
        html += f"<p>{format_invoice_number(rid)} — {client} — ${amount} <a href='/pdf/{rid}'>PDF</a></p>"
    return html

@app.route("/pdf/<int:invoice_id>")
def pdf(invoice_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT client, item, amount FROM invoices WHERE id=%s"
        if DATABASE_URL else
        "SELECT client, item, amount FROM invoices WHERE id=?",
        (invoice_id,)
    )
    invoice = c.fetchone()
    conn.close()

    if not invoice:
        return "Not found", 404

    path = f"invoice_{invoice_id}.pdf"
    pdf = canvas.Canvas(path, pagesize=LETTER)
    pdf.drawString(100, 750, f"Invoice {format_invoice_number(invoice_id)}")
    pdf.drawString(100, 720, f"Client: {invoice['client'] if DATABASE_URL else invoice[0]}")
    pdf.drawString(100, 700, f"Item: {invoice['item'] if DATABASE_URL else invoice[1]}")
    pdf.drawString(100, 680, f"Amount: ${invoice['amount'] if DATABASE_URL else invoice[2]}")
    pdf.save()

    return send_file(path, as_attachment=True)

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
    return redirect(session.url, code=303)

@app.route("/success")
def success():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE settings SET value='1' WHERE key='is_paid'"
    )
    conn.commit()
    conn.close()

    return "<h2>Payment successful 🎉</h2><a href='/'>Go home</a>"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)

    if event["type"] == "checkout.session.completed":
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE settings SET value='1' WHERE key='is_paid'")
        conn.commit()
        conn.close()

    return "", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)