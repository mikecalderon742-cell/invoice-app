import sqlite3
from flask import Flask, request, redirect, send_file
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

app = Flask(__name__)

DATABASE = "invoices.db"
FREE_LIMIT = 3

# ---------- DB INIT ----------
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client TEXT,
            item TEXT,
            amount TEXT
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

# ---------- ROUTES ----------
@app.route("/")
def home():
    count = invoice_count()
    paid = is_paid()

    remaining = "Unlimited" if paid else max(0, FREE_LIMIT - count)
    status = "Pro" if paid else f"Free ({remaining} left)"

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT id, client, item, amount FROM invoices")
    invoices = c.fetchall()
    conn.close()

    html = f"<h2>Invoice App</h2><p>Status: {status}</p>"

    if not paid and count >= FREE_LIMIT:
    html += """
    <p><b>Upgrade required to create more invoices</b></p>
    <form method="post" action="/upgrade">
        <button>Upgrade to Pro</button>
    </form>
    """

    else:
        html += """
        <form method="post" action="/create">
            Client <input name="client" required><br>
            Item <input name="item" required><br>
            Amount <input name="amount" required><br>
            <button>Create Invoice</button>
        </form>
        """

    html += "<hr>"

    for i in invoices:
        html += f"""
        <p>
            {i[1]} — {i[2]} — ${i[3]}
            <a href="/pdf/{i[0]}">PDF</a>
        </p>
        """

    return html

@app.route("/create", methods=["POST"])
def create():
    if not is_paid() and invoice_count() >= FREE_LIMIT:
        return redirect("/")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO invoices (client, item, amount) VALUES (?, ?, ?)",
        (request.form["client"], request.form["item"], request.form["amount"])
    )
    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/pdf/<int:invoice_id>")
def pdf(invoice_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "SELECT client, item, amount FROM invoices WHERE id=?",
        (invoice_id,)
    )
    invoice = c.fetchone()
    conn.close()

    if not invoice:
        return "Not found", 404

    path = f"invoice_{invoice_id}.pdf"
    pdf = canvas.Canvas(path, pagesize=LETTER)
    pdf.setFont("Helvetica", 12)

    pdf.drawString(100, 750, "Invoice")
    pdf.drawString(100, 720, f"Client: {invoice[0]}")
    pdf.drawString(100, 700, f"Item: {invoice[1]}")
    pdf.drawString(100, 680, f"Amount: ${invoice[2]}")

    pdf.save()

    return send_file(path, as_attachment=True)

@app.route("/upgrade", methods=["POST"])
def upgrade():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        "UPDATE settings SET value='1' WHERE key='is_paid'"
    )
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)