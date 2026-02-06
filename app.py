from flask import Flask, request, redirect

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h2>Invoice App</h2>
    <form method="post" action="/create">
        Client <input name="client" required><br>
        Item <input name="item" required><br>
        Amount <input name="amount" required><br>
        <button>Create Invoice</button>
    </form>
    """

@app.route("/create", methods=["POST"])
def create():
    return "<p>Invoice received ✅</p><a href='/'>Back</a>"

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
