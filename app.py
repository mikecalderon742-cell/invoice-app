import os
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, send_file
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import stripe

# ---------------- APP ----------------
app = Flask(__name__)

# ---------------- CONFIG ----------------
DATABASE = "invoices.db"
FREE_INVOICE_LIMIT = 3

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")

stripe.api_key = STRIPE_SECRET_KEY

# ---------------- DB ----------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
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
    c.execute("INSERT OR IGNORE INTO settings VALUES ('is_paid','0')")
    conn.commit()
    conn.close()

init_db()

# ---------------- HELPERS ----------------
def is_paid():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='is_paid'")
    v = c.fetchone()
    conn.close()
    return v and v[0] == "1"

def invoice_count():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM invoices")
    n = c.fetchone()[0]
    conn.close()
    return n

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    paid = is_paid()
    remaining = "Unlimited" if paid else FREE_INVOICE_LIMIT - invoice_count()
    return f"""
    <h2>Invoice App</h2>
    <p>Status: {'Pro' if paid else f'Free ({remaining} left)'}</p>
    <form method="post" action="/create">
        Client <input name="client"><br>
        Item <input name="item"><br>
        Amount <input name="amount"><br>
        <button>Create</button>
    </form>
    <a href="/invoices">Invoices</a><br>
    <a href="/upgrade">Upgrade</a>
    """

@app.route("/create", methods=["POST"])
def create():
    if not is_paid() and invoice_count() >= FREE_INVOICE_LIMIT:
        return redirect("/upgrade")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO invoices (client,item,amount) VALUES (?,?,?)",
        (request.form["client"], request.form["item"], request.form["amount"])
    )
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/invoices")
def invoices():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT id, client, item, amount FROM invoices")
    rows = c.fetchall()
    conn.close()

    html = "<h2>Invoices</h2>"
    for r in rows:
        html += f"<p>{r[1]} — ${r[3]} <a href='/pdf/{r[0]}'>PDF</a></p>"
    return html

@app.route("/pdf/<int:i>")
def pdf(i):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT client,item,amount FROM invoices WHERE id=?", (i,))
    row = c.fetchone()
    conn.close()

    if not row:
        return "Not found", 404

    path = f"invoice_{i}.pdf"
    p = canvas.Canvas(path, pagesize=LETTER)
    p.drawString(100, 750, f"Invoice {i}")
    p.drawString(100, 720, f"Client: {row[0]}")
    p.drawString(100, 700, f"Item: {row[1]}")
    p.drawString(100, 680, f"Amount: ${row[2]}")
    p.save()

    return send_file(path, as_attachment=True)

@app.route("/upgrade")
def upgrade():
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=f"{BASE_URL}/success",
        cancel_url=f"{BASE_URL}/"
    )
    return redirect(session.url, code=303)

@app.route("/success")
def success():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("UPDATE settings SET value='1' WHERE key='is_paid'")
    conn.commit()
    conn.close()

    return "<h2>Payment Successful 🎉</h2><a href='/'>Go Home</a>"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)

    if event["type"] == "checkout.session.completed":
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("UPDATE settings SET value='1' WHERE key='is_paid'")
        conn.commit()
        conn.close()

    return "", 200

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)