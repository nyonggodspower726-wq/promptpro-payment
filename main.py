import os
import uuid
import requests

from flask import Flask, request, jsonify, redirect

app = Flask(__name__)

# =========================================================
# FLUTTERWAVE V3 LIVE
# =========================================================

FLW_SECRET_KEY = os.environ.get("FLW_SECRET_KEY")

FLW_BASE_URL = "https://api.flutterwave.com/v3"

# Your Railway public URL will be added as a Railway Variable.
PAYMENT_SERVER_URL = os.environ.get("PAYMENT_SERVER_URL")

# Your GitHub success/failure pages
SUCCESS_URL = (
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/success.html"
)

FAILED_URL = (
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/payment-failed.html"
)


# =========================================================
# CORS
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
        "message": "PromptPro Hub payment server is online."
    })


# =========================================================
# CREATE PAYMENT
# =========================================================

@app.route("/create-payment", methods=["POST"])
def create_payment():

    if not FLW_SECRET_KEY:
        return jsonify({
            "status": "error",
            "message": "FLW_SECRET_KEY is not configured."
        }), 500

    if not PAYMENT_SERVER_URL:
        return jsonify({
            "status": "error",
            "message": "PAYMENT_SERVER_URL is not configured."
        }), 500

    data = request.get_json(silent=True) or {}

    currency = str(
        data.get("currency", "NGN")
    ).upper()

    email = data.get(
        "email",
        "customer@promptprohub.com"
    )

    # =====================================================
    # PRODUCT PRICES
    # =====================================================

    if currency == "NGN":

        # REAL TEST PRICE
        # Change to 19999 AFTER successful testing.
        amount = 100

    elif currency == "USD":

        # YOUR NORMAL USD PRICE
        amount = 14.99

    else:

        return jsonify({
            "status": "error",
            "message": "Only NGN and USD payments are supported."
        }), 400


    # =====================================================
    # UNIQUE TRANSACTION REFERENCE
    # =====================================================

    tx_ref = (
        "PROMPTPRO-"
        + currency
        + "-"
        + str(uuid.uuid4())
    )


    # =====================================================
    # REDIRECT AFTER FLUTTERWAVE PAYMENT
    # =====================================================

    callback_url = (
        PAYMENT_SERVER_URL.rstrip("/")
        + "/payment-callback"
    )


    # =====================================================
    # FLUTTERWAVE STANDARD PAYMENT
    # =====================================================

    payload = {
        "tx_ref": tx_ref,

        "amount": amount,

        "currency": currency,

        "redirect_url": callback_url,

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
        "Authorization": (
            f"Bearer {FLW_SECRET_KEY}"
        ),
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
    # PAYMENT LINK CREATED
    # =====================================================

    if (
        response.ok
        and result.get("status") == "success"
        and result.get("data")
        and result["data"].get("link")
    ):

        return jsonify({
            "status": "success",

            "payment_link": result["data"]["link"],

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
# PAYMENT CALLBACK
# =========================================================

@app.route("/payment-callback", methods=["GET"])
def payment_callback():

    status = request.args.get("status")
    tx_ref = request.args.get("tx_ref")
    transaction_id = request.args.get("transaction_id")


    # -----------------------------------------------------
    # PAYMENT FAILED / CANCELLED
    # -----------------------------------------------------

    if status != "successful":

        return redirect(FAILED_URL)


    # -----------------------------------------------------
    # REQUIRED INFORMATION
    # -----------------------------------------------------

    if not tx_ref or not transaction_id:

        return redirect(FAILED_URL)


    # -----------------------------------------------------
    # DETERMINE EXPECTED CURRENCY FROM TX REF
    # -----------------------------------------------------

    if "-NGN-" in tx_ref:

        expected_currency = "NGN"
        expected_amount = 100

    elif "-USD-" in tx_ref:

        expected_currency = "USD"
        expected_amount = 14.99

    else:

        return redirect(FAILED_URL)


    # -----------------------------------------------------
    # VERIFY WITH FLUTTERWAVE
    # -----------------------------------------------------

    headers = {
        "Authorization": (
            f"Bearer {FLW_SECRET_KEY}"
        ),
        "Content-Type": "application/json"
    }


    try:

        response = requests.get(
            f"{FLW_BASE_URL}/transactions/"
            f"{transaction_id}/verify",

            headers=headers,

            timeout=30
        )

        result = response.json()

    except Exception:

        return redirect(FAILED_URL)


    # -----------------------------------------------------
    # GET VERIFIED TRANSACTION
    # -----------------------------------------------------

    transaction = result.get("data", {})

    verified_status = transaction.get("status")

    verified_tx_ref = transaction.get("tx_ref")

    verified_currency = transaction.get("currency")

    verified_amount = transaction.get("amount")


    # -----------------------------------------------------
    # SECURITY CHECK
    # -----------------------------------------------------

    payment_is_valid = (
        result.get("status") == "success"
        and verified_status == "successful"
        and verified_tx_ref == tx_ref
        and verified_currency == expected_currency
        and float(verified_amount) >= float(expected_amount)
    )


    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    if payment_is_valid:

        return redirect(SUCCESS_URL)


    # -----------------------------------------------------
    # PAYMENT NOT VALID
    # -----------------------------------------------------

    return redirect(FAILED_URL)


# =========================================================
# SERVER
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 8080)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
