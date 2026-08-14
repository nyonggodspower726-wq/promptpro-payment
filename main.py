import os
import uuid
import requests

from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================================================
# CONFIGURATION
# =========================================================

FLW_SECRET_KEY = os.environ.get("FLW_SECRET_KEY")

FLW_BASE_URL = "https://api.flutterwave.com/v3"

CALLBACK_URL = (
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/payment-callback.html"
)


# =========================================================
# ALLOW YOUR GITHUB WEBSITE TO TALK TO RAILWAY
# =========================================================

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# =========================================================
# HOME / HEALTH CHECK
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "success",
        "message": "PromptPro Hub payment server is running."
    })


# =========================================================
# CREATE FLUTTERWAVE PAYMENT
# =========================================================

@app.route("/create-payment", methods=["POST"])
def create_payment():

    if not FLW_SECRET_KEY:
        return jsonify({
            "status": "error",
            "message": "Flutterwave Secret Key is not configured."
        }), 500

    data = request.get_json(silent=True) or {}

    currency = str(
        data.get("currency", "NGN")
    ).upper()

    # =====================================================
    # PRICES
    # =====================================================

    if currency == "NGN":

        # TEST PRICE
        # Change to 19999 after successful testing.
        amount = 100

    elif currency == "USD":

        # PRODUCT PRICE
        amount = 14.99

    else:

        return jsonify({
            "status": "error",
            "message": "Unsupported currency."
        }), 400


    # =====================================================
    # CUSTOMER
    # =====================================================

    email = data.get(
        "email",
        "customer@promptprohub.com"
    )


    # =====================================================
    # UNIQUE TRANSACTION REFERENCE
    # =====================================================

    tx_ref = "PROMPTPRO-" + str(uuid.uuid4())


    # =====================================================
    # FLUTTERWAVE REQUEST
    # =====================================================

    payload = {
        "tx_ref": tx_ref,
        "amount": amount,
        "currency": currency,

        "redirect_url": CALLBACK_URL,

        "customer": {
            "email": email
        },

        "customizations": {
            "title": "PromptPro Hub",
            "description": (
                "The Ultimate AI Business Toolkit"
            )
        }
    }


    headers = {
        "Authorization": f"Bearer {FLW_SECRET_KEY}",
        "Content-Type": "application/json"
    }


    try:

        response = requests.post(
            f"{FLW_BASE_URL}/payments",
            json=payload,
            headers=headers,
            timeout=30
        )

        result = response.json()

    except Exception as error:

        return jsonify({
            "status": "error",
            "message": "Could not connect to Flutterwave.",
            "details": str(error)
        }), 500


    # =====================================================
    # SUCCESS
    # =====================================================

    if (
        response.ok
        and result.get("status") == "success"
        and result.get("data")
        and result["data"].get("link")
    ):

        return jsonify({
            "status": "success",
            "link": result["data"]["link"],
            "tx_ref": tx_ref,
            "currency": currency,
            "amount": amount
        })


    # =====================================================
    # FLUTTERWAVE ERROR
    # =====================================================

    return jsonify({
        "status": "error",
        "message": "Flutterwave could not create the payment.",
        "flutterwave_response": result
    }), 400


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 8080)
    )

    app.run(
        host="0.0.0.0",
        port=port
)
