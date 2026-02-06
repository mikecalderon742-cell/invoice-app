from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>Invoice App is LIVE ✅</h1><p>If you see this, routing works.</p>"

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

