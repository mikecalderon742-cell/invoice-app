import os
from pathlib import Path

print("RUNNING FROM:", os.getcwd())

# Load .env explicitly (safe locally, ignored on Render)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path)
except Exception:
    pass

from flask import Flask, request, send_file, redirect
import sqlite3
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import stripe


# ---------- APP ----------
app = Flask(__name__)

# ---------- ENV / STRIPE ----------
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "").strip()
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
BASE_URL = os.environ.get("BASE_URL", "").strip()

if not STRIPE_SECRET_KEY:
    raise RuntimeError("STRIPE_SECRET_KEY missing")

if not STRIPE_PRICE_ID:
    raise RuntimeError("STRIPE_PRICE_ID missing")

if not STRIPE_WEBHOOK_SECRET:
    raise RuntimeError("STRIPE_WEBHOOK_SECRET missing")

if not BASE_URL:
    raise RuntimeError("BASE_URL missing")

stripe.api_key = STRIPE_SECRET_KEY


# ---------- APP CONFIG ----------
DATABASE = "invoices.db"
FREE_INVOICE_LIMIT = 3




# ================= STRIPE CONFIG =================


# =================================================


# ---------- DATABASE ----------


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




# ---------- HELPERS ----------
def is_paid():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("SELECT value FROM settings WHERE key = 'is_paid'")
    row = c.fetchone()

    conn.close()

    return row is not None and row[0] == "1"


from datetime import datetime

def format_invoice_number(invoice_id):
    year = datetime.now().year
    return f"{year}-INV-{str(invoice_id).zfill(4)}"

def get_user_status():
    return "Pro User ✅" if is_paid() else "Free User (3 invoices max)"

def get_user_status():
    if is_paid():
        return "Pro (Unlimited)"
    return f"Free ({FREE_INVOICE_LIMIT} invoices max)"

def invoice_count():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM invoices")
    count = c.fetchone()[0]
    conn.close()
    return count




# ---------- STYLES ----------

PAGE_STYLE = """
<style>
body {
    font-family: Arial, sans-serif;
    background: #f4f6f8;
    padding: 40px;
}
.container {
    max-width: 500px;
    background: white;
    padding: 30px;
    border-radius: 8px;
}
input, button {
    width: 100%;
    padding: 10px;
    margin-top: 6px;
}
button {
    background: #007bff;
    color: white;
    border: none;
    margin-top: 20px;
    cursor: pointer;
}
a {
    display: block;
    margin-top: 15px;
}
.invoice-card {
    border: 1px solid #e1e5ea;
    padding: 15px;
    border-radius: 6px;
    margin-bottom: 15px;
    background: #fafafa;
}

.invoice-number {
    font-weight: bold;
    font-size: 16px;
    margin-bottom: 6px;
}

.invoice-meta {
    color: #555;
    margin-bottom: 8px;
}

.invoice-actions a {
    font-size: 14px;
    text-decoration: none;
    color: #007bff;
}

</style>
"""

FOOTER = """
<footer style="margin-top:40px; text-align:center; font-size:12px; color:#777;">
    © 2026 Mike Calderon — Invoice Generator
</footer>
"""


# ---------- ROUTES ----------

@app.route("/")
def home():
    count = invoice_count()
    paid = is_paid()

    limit_reached = (not paid and count >= FREE_INVOICE_LIMIT)

    status = "Pro (Unlimited)" if paid else f"Free ({FREE_INVOICE_LIMIT - count} invoices left)"

    button_html = """
        <button type="submit">Save Invoice</button>
    """

    if limit_reached:
        button_html = """
            <button type="submit" disabled style="background:#ccc; cursor:not-allowed;">
                Free Limit Reached
            </button>
            <p style="color:#c00; margin-top:10px;">
                You’ve reached the free limit.
                <a href="/upgrade">Upgrade to continue</a>
            </p>
        """

    return PAGE_STYLE + f"""
    <div class="container">
        <h2>Create Invoice</h2>

        <p style="color:#666; font-size:14px;">
            Status: {status}
        </p>

        <form method="post" action="/create">
            Client Name
            <input type="text" name="client" required>

            Item
            <input type="text" name="item" required>

            Amount ($)
            <input type="number" name="amount" required>

            {button_html}
        </form>

        <a href="/invoices">View All Invoices</a>
    </div>
    """ + FOOTER




@app.route("/create", methods=["POST"])
def create():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM invoices")
    count = c.fetchone()[0]

    if not is_paid() and count >= FREE_INVOICE_LIMIT:

        conn.close()
        return PAGE_STYLE + """
        <div class="container">
            <h2>Free Limit Reached</h2>
            <p>You’ve created the maximum of 3 free invoices.</p>

            <a href="/upgrade">Upgrade to create unlimited invoices</a>
            <a href="/invoices">View your invoices</a>
        </div>
        """ + FOOTER

    client = request.form["client"]
    item = request.form["item"]
    amount = request.form["amount"]

    c.execute(
        "INSERT INTO invoices (client, item, amount) VALUES (?, ?, ?)",
        (client, item, amount)
    )
    invoice_id = c.lastrowid
    conn.commit()
    conn.close()

    return PAGE_STYLE + f"""
    <div class="container">
        <h2>Invoice Saved</h2>
        <p><strong>Invoice {format_invoice_number(invoice_id)}</strong></p>
        <p><strong>{client}</strong></p>
        <p>{item}</p>
        <p>${amount}</p>

        <a href="/pdf/{invoice_id}">Download PDF</a>
        <a href="/invoices">View all invoices</a>
        <a href="/">Create another</a>
    </div>
    """ + FOOTER


@app.route("/invoices")
def invoices():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT id, client, item, amount FROM invoices ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()

    html = PAGE_STYLE + """
    <div class="container">
        <h2>All Invoices</h2>
    """

    if not rows:
        html += """
        <p style="color:#666; text-align:center;">
            No invoices yet. Create your first one 👇
        </p>
        <a href="/">Create Invoice</a>
        </div>
        """
        return html + FOOTER

    for r in rows:
        html += f"""
        <div class="invoice-card">
            <div class="invoice-number">
                {format_invoice_number(r[0])}
            </div>

            <div class="invoice-meta">
                <strong>{r[1]}</strong><br>
                {r[2]} — ${r[3]}
            </div>

            <div class="invoice-actions">
                <a href="/pdf/{r[0]}">Download PDF</a>
            </div>
        </div>
        """

    html += "<a href='/'>Back</a></div>"
    return html + FOOTER


@app.route("/pdf/<int:invoice_id>")
def pdf(invoice_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Count invoices
    c.execute("SELECT COUNT(*) FROM invoices")
    count = c.fetchone()[0]

    # Block PDF if over free limit
    if count > FREE_INVOICE_LIMIT and not is_paid():
        conn.close()
        return PAGE_STYLE + """
        <div class="container">
            <h2>Upgrade Required 🔒</h2>
            <p>
                You’ve reached the free invoice limit.<br>
                Upgrade to unlock unlimited invoices and PDF downloads.
            </p>

            <a href="/upgrade">Upgrade Now</a>
            <a href="/invoices">Back to invoices</a>
        </div>
        """ + FOOTER

    # Otherwise generate PDF
    c.execute(
        "SELECT client, item, amount FROM invoices WHERE id = ?",
        (invoice_id,)
    )
    invoice = c.fetchone()
    conn.close()

    if not invoice:
        return "Invoice not found", 404

    filename = f"invoice_{invoice_id}.pdf"
    file_path = os.path.join(os.getcwd(), filename)

    pdf = canvas.Canvas(file_path, pagesize=LETTER)
    pdf.setFont("Helvetica", 12)

    pdf.drawString(100, 750, f"INVOICE {format_invoice_number(invoice_id)}")
    pdf.drawString(100, 700, f"Client: {invoice[0]}")
    pdf.drawString(100, 680, f"Item: {invoice[1]}")
    pdf.drawString(100, 660, f"Amount: ${invoice[2]}")

    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(300, 30, "© 2026 Mike Calderon — Invoice Generator")

    pdf.showPage()
    pdf.save()

    return send_file(file_path, as_attachment=True)





# ---------- STRIPE ROUTES ----------

@app.route("/upgrade")
def upgrade():
    try:
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

    except Exception as e:
        # SHOW THE REAL STRIPE ERROR
        return f"""
        <h2>Stripe Error</h2>
        <pre>{str(e)}</pre>
        """, 500



@app.route("/success")
def success():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("""
        UPDATE settings
        SET value = '1'
        WHERE key = 'is_paid'
    """)
    conn.commit()
    conn.close()

    return PAGE_STYLE + """
    <div class="container">
        <h2>Payment Successful 🎉</h2>
        <p>You now have unlimited invoices and PDF downloads.</p>

        <a href="/">Create invoice</a>
        <a href="/invoices">View invoices</a>
    </div>
    """ + FOOTER


# ---------- RUN ----------
from flask import abort
import json

@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    event = stripe.Webhook.construct_event(
        payload,
        sig_header,
        STRIPE_WEBHOOK_SECRET
    )

    if event["type"] == "checkout.session.completed":
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        c.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES ('is_paid', '1')
        """)

        conn.commit()
        conn.close()

    return "", 200



# ---------- RUN ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)



