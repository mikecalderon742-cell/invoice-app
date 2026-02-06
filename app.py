from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "APP IS RUNNING"

@app.route("/success")
def success():
    return "SUCCESS PAGE WORKS"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)