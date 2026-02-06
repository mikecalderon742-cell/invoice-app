print(">>> APP.PY LOADED <<<")

from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>Invoice App is LIVE ✅</h1>
    <p>If you see this, routing works.</p>
    <p><a href="/success">Test /success</a></p>
    <p><a href="/upgrade">Test /upgrade</a></p>
    """

@app.route("/success")
def success():
    return """
    <h1>SUCCESS PAGE ✅</h1>
    <p>You reached /success correctly.</p>
    <a href="/">Back home</a>
    """

@app.route("/upgrade")
def upgrade():
    return """
    <h1>Upgrade Page ✅</h1>
    <p>This is just a placeholder for now.</p>
    <a href="/">Back home</a>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
