import sqlite3
from flask import Flask, request, redirect

app = Flask(__name__)

DATABASE = "invoices.db"

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
    conn.commit()
    conn.close()

init_db()

# ---------- ROUTES ----------
@app.route("/")
def home():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT client, item, amount FROM invoices")
    invoices = c.fetchall()
    conn.close()

    html = "<h2>Invoice App</h2>"

    html += """
    <form method="post" action="/create">
        Client <input name="client" required><br>
        Item <input name="item" required><br>
        Amount <input name="amount" required><br>
        <button>Create Invoice</button>
    </form>
    <hr>
    """

    for i in invoices:
        html += f"<p>{i[0]} — {i[1]} — ${i[2]}</p>"

    return html

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

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)