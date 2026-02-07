print(">>> APP.PY LOADED <<<")

import os
import sqlite3
import stripe
from flask import Flask, request, redirect, send_file, abort
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from datetime import datetime

# ======================
# App configuration
# ======================

app = Flask(__name__)

BASE_URL = os.environ.get("BASE_URL", "http://localhost:10000")
print("BASE_URL =", BASE_URL)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

DB_PATH = "invoices.db"
FREE_INVOICE_LIMIT = 3

# ======================
# Database helpers
# ======================

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
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

    con.commit()
    con.close()

init_db()

def get_setting(key):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else None

def set_setting(key, value):
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )
    con.commit()
    con.close()

# ======================
# Stripe logic
# ======================

def is_paid():
    customer_id = get_setting("stripe_customer_id")
    if not customer_id:
        return False

    try:
        subs = stripe.Subscription.list(
            customer=customer_id,
            status="active",
            limit=1
        )
        return len(subs.data) > 0
    except Exception as e:
        print("Stripe error:", e)
        return False

# ======================
# Invoice logic
# ======================

def invoice_count():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM invoices")
    count = cur.fetchone()[0]
    con.close()
    return count

def can_create_invoice():
    return is_paid() or invoice_count() < FREE_INVOICE_LIMIT

# ======================
# Routes
# ======================

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def home():
    paid = is_paid()
    count = invoice_count()

    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, item, client, amount FROM invoices ORDER BY id DESC")
    invoices = cur.fetchall()
    con.close()

    html = "<h1>Invoice App</h1>"

    if paid:
        html += "<p><strong>Premium account ✅</strong></p>"
    else:
        remaining = FREE_INVOICE_LIMIT - count
        html += f"<p>Free invoices remaining: {remaining}</p>"
        html += "<a href='/upgrade'>Upgrade to Pro</a><br><br>"

    html += """
        <h3>Create Invoice</h3>
        <form method="POST" action="/create">
            Item: <input name="item" required><br>
            Client: <input name="client" required><br>
            Amount: <input name="amount" type="number" step="0.01" required><br>
            <button type="submit">Create Invoice</button>
        </form>
        <hr>
        <h3>Invoices</h3>
    """

    for inv in invoices:
        html += f"""
            <p>
                #{inv[0]} — {inv[1]} — {inv[2]} — ${inv[3]}
                <a href="/pdf/{inv[0]}">Download PDF</a>
            </p>
        """

    return html

@app.route("/create", methods=["POST"])
def create():
    if not can_create_invoice():
        return redirect("/upgrade")

    item = request.form["item"]
    client = request.form["client"]
    amount = request.form["amount"]

    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO invoices (item, client, amount, created_at) VALUES (?, ?, ?, ?)",
        (item, client, amount, datetime.utcnow().isoformat())
    )
    con.commit()
    con.close()

    return redirect("/")

@app.route("/pdf/<int:invoice_id>")
def pdf(invoice_id):
    con = db()
    cur = con.cursor()
    cur.execute(
        "SELECT item, client, amount, created_at FROM invoices WHERE id=?",
        (invoice_id,)
    )
    row = cur.fetchone()
    con.close()

    if not row:
        abort(404)

    item, client, amount, created_at = row

    filename = f"invoice_{invoice_id}.pdf"
    c = canvas.Canvas(filename, pagesize=LETTER)

    c.drawString(100, 750, "Invoice")
    c.drawString(100, 720, f"Item: {item}")
    c.drawString(100, 700, f"Client: {client}")
    c.drawString(100, 680, f"Amount: ${amount}")
    c.drawString(100, 660, f"Date: {created_at}")

    c.save()
    return send_file(filename, as_attachment=True)

# ======================
# Stripe checkout
# ======================

@app.route("/upgrade")
def upgrade():
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{
            "price": STRIPE_PRICE_ID,
            "quantity": 1
        }],
        success_url=BASE_URL + "/success",
        cancel_url=BASE_URL,
    )
    return redirect(session.url, code=303)

@app.route("/success")
def success():
    return "<h1>Payment successful 🎉</h1><a href='/'>Return home</a>"

# ======================
# Stripe webhook (CRITICAL)
# ======================

@app.route("/webhook", methods=["POST"])
def webhook():
    print(">>> WEBHOOK HIT <<<")

    payload = request.data
    sig = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig,
            STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("❌ WEBHOOK VERIFY FAILED:", e)
        return "Invalid", 400

    print("EVENT TYPE:", event["type"])

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_id = session.get("customer")
        print(">>> CHECKOUT COMPLETED <<<", customer_id)

        if customer_id:
            set_setting("stripe_customer_id", customer_id)

    return "OK", 200

# ======================
# Local run
# ======================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)