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
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")

if not STRIPE_SECRET_KEY:
    raise RuntimeError("STRIPE_SECRET_KEY missing")
if not STRIPE_PRICE_ID:
    raise RuntimeError("STRIPE_PRICE_ID missing")
if not BASE_URL:
    raise RuntimeError("BASE_URL missing")

stripe.api_key = STRIPE_SECRET_KEY

# ---------------- DATABASE ----------------
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

    c.execute("""
        INSERT OR IGNORE INTO settings (key, value)
        VALUES ('is_paid', '0')
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HELPERS ----------------
def is_paid():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='is_paid'")
    row = c.fetchone()
    conn.close()
    return row and row[0] == "1"

def invoice_count():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM invoices")
    count = c.fetchone()[0]
    conn.close()
    return count

def invoice_number(invoice_id):
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
    <h2>Create Invoice</h2>
    <p>Status: {status}</p>

    <form method="post" action="/create">
        Client <input name="client" required><br>
        Item <input name="item" required><br>
        Amount <input name="amount" required><br>
        <button>Create</button>
    </form>

    {upgrade_link}
    <p><a href="/invoices">View invoices</a></p>
    """

@app.route("/create", methods=["POST"])
def create():
    if not is_paid() and invoice_count() >= FREE_INVOICE_LIMIT:
        return redirect("/upgrade")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO invoices (client, item, amount) VALUES (?, ?, ?)",
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
        html += f"<p>{invoice_number(r[0])} — {r[1]} — ${r[3]} <a href='/pdf/{r[0]}'>PDF</a></p>"
    html += "<p><a href='/'>Back</a></p>"
    return html

@app.route("/pdf/<int:invoice_id>")
def pdf(invoice_id):
    if not is_paid() and invoice_count() > FREE_INVOICE_LIMIT:
        return redirect("/upgrade")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT client, item, amount FROM invoices WHERE id=?", (invoice_id,))
    invoice = c.fetchone()
    conn.close()

    if not invoice:
        return "Not found", 404

    filename = f"invoice_{invoice_id}.pdf"
    pdf = canvas.Canvas(filename, pagesize=LETTER)
    pdf.setFont("Helvetica", 12)

    pdf.drawString(100, 750, f"Invoice {invoice_number(invoice_id)}")
    pdf.drawString(100, 720, f"Client: {invoice[0]}")
    pdf.drawString(100, 700, f"Item: {invoice[1]}")
    pdf.drawString(100, 680, f"Amount: ${invoice[2]}")

    pdf.save()
    return send_file(filename, as_attachment=True)

# ---------------- STRIPE ----------------
@app.route("/upgrade")
def upgrade():
    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
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
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO settings (key, value)
        VALUES ('is_paid', '1')
    """)
    conn.commit()
    conn.close()

    return """
    <h2>Payment Successful 🎉</h2>
    <p>You now have unlimited invoices.</p>
    <p><a href="/">Go home</a></p>
    """

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
