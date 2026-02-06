from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>Home page ✅</h1><a href='/upgrade'>Upgrade</a>"

@app.route("/upgrade")
def upgrade():
    return "<h1>Upgrade page works ✅</h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

