print(">>> APP.PY LOADED <<<")

import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, send_file
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

app = Flask(__name__)

DATABASE = "invoices.db"

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
    conn.commit()
    conn.close()

init_db()

# ---------- HELPERS ----------
def format_invoice_number(invoice_id):
    return f"{datetime.now().year}-INV-{str(invoice_id).zfill(4)}"

# ---------- ROUTES ----------
@app.route("/")
def home():
    return """
    <h2>Create Invoice</h2>
    <form method="post" action="/create">
        Client <input name="client" required><br>
        Item <input name="item" required><br>
        Amount <input name="amount" required><br>
        <button>Create</button>
    </form>
    <br>
    <a href="/invoices">View invoices</a>
    """

@app.route("/create", methods=["POST"])
def create():
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
        html += f"<p>{format_invoice_number(r[0])} — {r[1]} — ${r[3]} <a href='/pdf/{r[0]}'>PDF</a></p>"
    html += "<br><a href='/'>Back</a>"
    return html

@app.route("/pdf/<int:invoice_id>")
def pdf(invoice_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT client, item, amount FROM invoices WHERE id=?", (invoice_id,))
    invoice = c.fetchone()
    conn.close()

    if not invoice:
        return "Not found", 404

    path = f"invoice_{invoice_id}.pdf"
    pdf = canvas.Canvas(path, pagesize=LETTER)
    pdf.drawString(100, 750, f"Invoice {format_invoice_number(invoice_id)}")
    pdf.drawString(100, 720, f"Client: {invoice[0]}")
    pdf.drawString(100, 700, f"Item: {invoice[1]}")
    pdf.drawString(100, 680, f"Amount: ${invoice[2]}")
    pdf.save()

    return send_file(path, as_attachment=True)

@app.route("/success")
def success():
    return "<h1>SUCCESS PAGE ✅</h1><a href='/'>Home</a>"

@app.route("/upgrade")
def upgrade():
    return "<h1>Upgrade placeholder</h1><a href='/'>Home</a>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)