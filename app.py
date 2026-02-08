import os
import json
from flask import Flask, render_template, redirect, url_for, request
import stripe

# -------------------------------------------------
# App setup
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

BASE_URL = os.environ.get(
    "BASE_URL",
    "http://localhost:10000"
)

# -------------------------------------------------
# Stripe setup
# -------------------------------------------------
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")

# -------------------------------------------------
# VERY SIMPLE USER STORAGE (single-user app)
# -------------------------------------------------