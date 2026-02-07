import os
import stripe
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
from flask import Flask, request, session, redirect, render_template

# -------------------------
# App setup
# -------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

print(">>> APP.PY LOADED <<<")
print("BASE_URL =", os.environ.get("BASE_URL"))

# -------------------------
# Database helpers (Step 1.2)
# -------------------------
def get_db():
    url = urlparse(os.environ["DATABASE_URL"])
    return psycopg2.connect(
        dbname=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port,
        cursor_factory=RealDictCursor,
    )

# -------------------------
# Init DB + users table (Step 1.3)
# -------------------------
def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    stripe_customer_id TEXT UNIQUE,
                    is_pro BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()

init_db()

# -------------------------
# User loader / creator (Step 1.4)
# -------------------------
def get_current_user():
    user_id = session.get("user_id")

    with get_db() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                if user:
                    return user

            # create new user
            cur.execute("INSERT INTO users DEFAULT VALUES RETURNING *")
            user = cur.fetchone()
            session["user_id"] = user["id"]
            conn.commit()
            return user

# -------------------------
# Routes
# -------------------------
@app.route("/")
def home():
    user = get_current_user()
    return render_template(
        "index.html",
        is_pro=user["is_pro"]
    )

@app.route("/upgrade")
def upgrade():
    user = get_current_user()

    checkout_session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        success_url=os.environ["BASE_URL"] + "/success",
        cancel_url=os.environ["BASE_URL"],
    )

    return redirect(checkout_session.url, code=303)

@app.route("/success")
def success():
    return render_template("success.html")

# -------------------------
# Stripe webhook (Step 1.6)
# -------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            os.environ["STRIPE_WEBHOOK_SECRET"],
        )
    except Exception as e:
        print("Webhook verification failed:", e)
        return "Invalid signature", 400

    print(">>> WEBHOOK HIT <<<")
    print("EVENT TYPE:", event["type"])

    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        customer_id = session_obj.get("customer")

        if customer_id:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE users
                        SET is_pro = TRUE,
                            stripe_customer_id = %s
                        WHERE id = (
                            SELECT id FROM users
                            ORDER BY created_at DESC
                            LIMIT 1
                        )
                    """, (customer_id,))
                conn.commit()

            print(">>> CHECKOUT COMPLETED <<<", customer_id)

    return "ok", 200

# -------------------------
# Health check (Render)
# -------------------------
@app.route("/health")
def health():
    return "ok", 200