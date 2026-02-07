import os
import psycopg2
from flask import Flask, request, redirect, send_file
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import stripe
from io import BytesIO

print(">>> APP.PY LOADED <<<")

# --------------------
# Config
# --------------------

BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
DATABASE_URL = os.environ.get("DATABASE_URL")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

FREE_LIMIT = 3

if not BASE_URL:
    raise RuntimeError("BASE_URL missing")

stripe.api_key = STRIPE_SECRET_KEY

print("BASE_URL =", BASE_URL)

app = Flask(__name__)

# --------------------
# Database
# --------------------

def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            client TEXT,
            amount TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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

# --------------------
# Routes
# --------------------

@app.route("/")
def home():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT value FROM settings WHERE key='is_paid'")
    is_paid = cur.fetchone()[0] == "1"

    cur.execute("SELECT COUNT(*) FROM invoices")
    count = cur.fetchone()[0]

    conn.close()

    if not is_paid and count >= FREE_LIMIT:
        return """
        <h2>Free limit reached</h2>
        <p>You’ve used all free invoices.</p>
        <a href="/upgrade">Upgrade to Pro</a>
        """

    return """
    <h1>Create Invoice</h1>

    <form method="POST" action="/create">
        <label>Client</label><br>
        <input name="client" required><br><br>

        <label>Amount</label><br>
        <input name="amount" required><br><br>

        <button type="submit">Create Invoice</button>
    </form>

    <br>
    <a href="/invoices">View invoices</a>
    """

@app.route("/create", methods=["POST"])
def create():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO invoices (client, amount)
        VALUES (%s, %s)
    """, (request.form["client"], request.form["amount"]))

    conn.commit()
    conn.close()

    return redirect("/invoices")

@app.route("/invoices")
def invoices():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, client, amount FROM invoices ORDER BY id DESC")
    rows = cur.fetchall()

    conn.close()

    html = "<h1>Invoices</h1><ul>"
    for r in rows:
        html += f"<li>{r[1]} – ${r[2]} <a href='/pdf/{r[0]}'>PDF</a></li>"
    html += "</ul><br><a href='/'>Back</a>"

    return html

@app.route("/pdf/<int:invoice_id>")
def pdf(invoice_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT client, amount FROM invoices WHERE id=%s",
        (invoice_id,)
    )
    row = cur.fetchone()
    conn.close()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)

    p.drawString(100, 700, f"Client: {row[0]}")
    p.drawString(100, 680, f"Amount: ${row[1]}")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(buffer, download_name="invoice.pdf", as_attachment=True)

# --------------------
# Stripe
# --------------------

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
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE settings SET value='1' WHERE key='is_paid'"
    )

    conn.commit()
    conn.close()

    return """
    <h1>Payment successful ✅</h1>
    <a href="/">Go back to app</a>
    """

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")

    event = stripe.Webhook.construct_event(
        payload, sig, STRIPE_WEBHOOK_SECRET
    )

    if event["type"] == "checkout.session.completed":
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE settings SET value='1' WHERE key='is_paid'"
        )
        conn.commit()
        conn.close()

    return "", 200

# --------------------
# Run
# --------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)