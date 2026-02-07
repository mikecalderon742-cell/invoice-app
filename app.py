import os
from flask import Flask, render_template, redirect, session, url_for
import stripe

app = Flask(__name__)

# ======================
# CONFIG
# ======================
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")

print(">>> APP.PY LOADED <<<")
print("BASE_URL =", BASE_URL)

# ======================
# HELPERS
# ======================
def get_current_user():
    # Simple session-based user for now
    if "user" not in session:
        session["user"] = {
            "is_pro": False
        }
    return session["user"]

# ======================
# ROUTES
# ======================
@app.route("/")
def home():
    user = get_current_user()
    return render_template(
        "index.html",
        is_pro=user["is_pro"]
    )

@app.route("/checkout")
def checkout():
    """
    This matches <a href="/checkout">Upgrade to Pro</a>
    """
    checkout_session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price": STRIPE_PRICE_ID,
                "quantity": 1,
            }
        ],
        success_url=f"{BASE_URL}/success",
        cancel_url=f"{BASE_URL}/",
    )

    return redirect(checkout_session.url, code=303)

@app.route("/success")
def success():
    user = get_current_user()
    user["is_pro"] = True
    session["user"] = user
    return redirect(url_for("home"))

@app.route("/health")
def health():
    return "OK", 200

# ======================
# LOCAL DEV
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)