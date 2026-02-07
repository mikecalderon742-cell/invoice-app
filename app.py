print(">>> APP.PY LOADED <<<")

import os
import sqlite3
import stripe
from flask import Flask, request, redirect, url_for, send_file, abort
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from datetime import datetime

# ------------------------
# App + Config
# ------------------------

app = Flask(__name__)

BASE_URL = os.environ.get("BASE_URL", "http://localhost:10000")
print("BASE_URL =", BASE_URL)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

DB_PATH = "invoices.db"

FREE_INVOICE_LIMIT = 3

# ------------------------
# Database Helpers
# ------------------------

def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client TEXT,
            amount REAL,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    db.commit()
    db.close()

init_db()

def get_setting(key):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    db.close()
    return row[0] if row else None

def set_setting(key, value):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    db.commit()
    db.close()

# ------------------------
# Stripe Logic (SOURCE OF TRUTH)
# ------------------------

def stripe_subscription_active():
    customer_id = get_setting("stripe_customer_id")
    if not customer_id:
        return False

    try:
        subs = stripe.Subscription.list(customer=customer_id, status="active")
        return len(subs.data) > 0
    except Exception as e:
        print("Stripe check failed:", e)
        return False

def is_paid():
    return stripe_subscription_active()

# ------------------------
# Invoice Logic
# ------------------------

def invoice_count():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM invoices")
    count = cur.fetchone()[0]
    db.close()
    return count

def can_create_invoice():
    if is_paid():
        return True
    return invoice_count() < FREE_INVOICE_LIMIT

# ------------------------
# Routes
# ------------------------

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def home():
    count = invoice_count()
    paid = is_paid()

    html = "<h1>Invoice App is LIVE ✅</h1>"
    html += f"<p>Invoices created: {count}</p>"

    if not paid:
        html += f"<p>Free limit: {FREE_INVOICE_LIMIT}</p>"
        html += "<a href='/upgrade'>Upgrade</a><br><br>"
    else:
        html += "<p><strong>Premium unlocked ✅</strong></p><br>"

    html += """
        <form method="POST" action="/create">
            Client Name: <input name="client"><br>
            Amount: <input name="amount" type="number" step="0.01"><br>
            <button type="submit">Create Invoice</button>
        </form>
    """

    return html

@app.route("/create", methods=["POST"])
def create_invoice():
    if not can_create_invoice():
        return redirect("/upgrade")

    client = request.form["client"]
    amount = request.form["amount"]
    created_at = datetime.utcnow().isoformat()

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO invoices (client, amount, created_at) VALUES (?, ?, ?)",
        (client, amount, created_at),
    )
    invoice_id = cur.lastrowid
    db.commit()
    db.close()

    return redirect(f"/pdf/{invoice_id}")

@app.route("/pdf/<int:invoice_id>")
def pdf(invoice_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT client, amount, created_at FROM invoices WHERE id=?", (invoice_id,))
    row = cur.fetchone()
    db.close()

    if not row:
        abort(404)

    client, amount, created_at = row

    filename = f"invoice_{invoice_id}.pdf"
    c = canvas.Canvas(filename, pagesize=LETTER)

    c.drawString(100, 750, "Invoice")
    c.drawString(100, 720, f"Client: {client}")
    c.drawString(100, 700, f"Amount: ${amount}")
    c.drawString(100, 680, f"Date: {created_at}")

    c.save()

    return send_file(filename, as_attachment=True)

@app.route("/upgrade")
def upgrade():
    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{
            "price": os.environ.get("STRIPE_PRICE_ID"),
            "quantity": 1
        }],
        success_url=BASE_URL + "/success",
        cancel_url=BASE_URL,
    )
    return redirect(session.url, code=303)

@app.route("/success")
def success():
    return "<h1>Payment successful 🎉</h1><a href='/'>Return Home</a>"

# ------------------------
# Stripe Webhook
# ------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig,
            os.environ.get("STRIPE_WEBHOOK_SECRET")
        )
    except Exception as e:
        print("Webhook error:", e)
        return "Invalid", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_id = session.get("customer")
        if customer_id:
            set_setting("stripe_customer_id", customer_id)

    return "OK", 200

# ------------------------
# Local Run
# ------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)