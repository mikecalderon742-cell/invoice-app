import os
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, send_file
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

print(">>> APP.PY LOADED <<<")

# --------------------
# App setup
# --------------------
app = Flask(__name__)

DATABASE = "invoices.db"
FREE_INVOICE_LIMIT = 3

# --------------------
# Health check (RENDER)
# --------------------
@app.route("/health")
def health():
    return "OK", 200

# --------------------
# Database
# --------------------
def get_db():
    return sqlite3.connect(DATABASE)

def init_db():
    conn = get_db()
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

# --------------------
# Helpers
# --------------------
def is_paid():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='is_paid'")
    row = c.fetchone()
    conn.close()
    return row and row[0] == "1"

def invoice_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM invoices")
    count = c.fetchone()[0]
    conn.close()
    return count

def invoice_number(i):
    return f"{datetime.now().year}-INV-{str(i).zfill(4)}"

# --------------------
# Routes
# --------------------
@app.route("/")
def home():
    paid = is_paid()
    count = invoice_count()

    status = "Pro (Unlimited)" if paid else f"Free ({FREE_INVOICE_LIMIT - count} left)"

    upgrade_notice = ""
    if not paid:
        upgrade_notice = "<p><b>Upgrade coming soon</b></p>"

    return f"""
    <h1>Invoice App</h1>
    <p>Status: {status}</p>

    <form method="post" action="/create">
        Client: <input name="client" required><br>
        Item: <input name="item" required><br>
        Amount: <input name="amount" required><br>
        <button>Create Invoice</button>
    </form>

    {upgrade_notice}

    <p><a href="/invoices">View invoices</a></p>
    """

@app.route("/create", methods=["POST"])
def create():
    if not is_paid() and invoice_count() >= FREE_INVOICE_LIMIT:
        return "<h2>Free limit reached</h2><p>Upgrade required</p>"

    conn = get_db()
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
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, client, item, amount FROM invoices")
    rows = c.fetchall()
    conn.close()

    html = "<h2>Invoices</h2>"
    for r in rows:
        html += f"""
        <p>
            {invoice_number(r[0])} — {r[1]} — ${r[3]}
            <a href="/pdf/{r[0]}">PDF</a>
        </p>
        """
    html += '<p><a href="/">Back</a></p>'
    return html

@app.route("/pdf/<int:invoice_id>")
def pdf(invoice_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT client, item, amount FROM invoices WHERE id=?",
        (invoice_id,)
    )
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

# --------------------
# Run
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)