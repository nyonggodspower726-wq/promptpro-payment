import os
import uuid
import requests

from flask import Flask, request, jsonify, redirect

app = Flask(__name__)

# =========================================================
# FLUTTERWAVE STANDARD HOSTED CHECKOUT
# =========================================================

FLW_SECRET_KEY = os.environ.get("FLW_SECRET_KEY")

FLW_API_URL = "https://api.flutterwave.com/v3/payments"

FLW_VERIFY_URL = "https://api.flutterwave.com/v3/transactions"


# =========================================================
# YOUR GITHUB PAGES
# =========================================================

SUCCESS_URL = (
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/success.html"
)

FAILED_URL = (
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/payment-failed.html"
)


# =========================================================
# PRODUCT
# =========================================================

PRODUCT_NAME = "PromptPro Hub - The Ultimate AI Business Toolkit"


# =========================================================
# CORS
# =========================================================

@app.after_request
def add_cors_headers(response):

    response.headers["Access-Control-Allow-Origin"] = "*"

    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type"
    )

    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, OPTIONS"
    )

    return response


# =========================================================
# HOME
# =========================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "success",
        "message": "PromptPro Hub hosted payment server is running.",
        "payment_system": "Flutterwave Standard Hosted Checkout"
    })


# =========================================================
# CREATE PAYMENT
# =========================================================

@app.route("/create-payment", methods=["POST"])
def create_payment():

    # -----------------------------------------------------
    # Check secret key
    # -----------------------------------------------------

    if not FLW_SECRET_KEY:

        return jsonify({
            "status": "error",
            "message": (
                "FLW_SECRET_KEY is not configured "
                "in Railway Variables."
            )
        }), 500


    # -----------------------------------------------------
    # Read request
    # -----------------------------------------------------

    data = request.get_json(silent=True) or {}


    currency = str(
        data.get("currency", "NGN")
    ).upper()


    email = str(
        data.get(
            "email",
            "customer@promptprohub.com"
        )
    ).strip()


    name = str(
        data.get(
            "name",
            "PromptPro Hub Customer"
        )
    ).strip()


    # -----------------------------------------------------
    # PAYMENT AMOUNT
    # -----------------------------------------------------

    if currency == "NGN":

        # ₦100 TEST PRICE
        #
        # AFTER TESTING:
        # CHANGE 100 TO 19999

        amount = 100


    elif currency == "USD":

        amount = 14.99


    else:

        return jsonify({
            "status": "error",
            "message": (
                "Only NGN and USD "
                "payments are supported."
            )
        }), 400


    # -----------------------------------------------------
    # UNIQUE TRANSACTION REFERENCE
    # -----------------------------------------------------

    tx_ref = (
        "PROMPTPRO-"
        + currency
        + "-"
        + uuid.uuid4().hex[:20]
    )


    # -----------------------------------------------------
    # FLUTTERWAVE STANDARD PAYMENT
    # -----------------------------------------------------

    payload = {

        "tx_ref": tx_ref,

        "amount": amount,

        "currency": currency,

        # Flutterwave will redirect here AFTER payment.
        #
        # Railway verifies the transaction first,
        # then sends the customer to your GitHub page.

        "redirect_url": (
            "https://promptpro-payment-production-f97b"
            ".up.railway.app/payment-callback"
        ),

        "customer": {

            "email": email,

            "name": name

        },

        "customizations": {

            "title": PRODUCT_NAME,

            "description": (
                "Premium AI prompts, "
                "business templates and "
                "bonus resources."
            )

        },

        "payment_options": (
            "card,banktransfer,ussd"
        ),

        "configurations": {

            "session_duration": 30,

            "max_retry_attempt": 5

        },

        "meta": {

            "product": "PromptPro Hub",

            "product_type": "digital_product",

            "currency": currency,

            "amount": amount

        }

    }


    # -----------------------------------------------------
    # SEND TO FLUTTERWAVE
    # -----------------------------------------------------

    headers = {

        "Authorization": (
            "Bearer "
            + FLW_SECRET_KEY
        ),

        "Content-Type": "application/json"

    }


    try:

        response = requests.post(

            FLW_API_URL,

            headers=headers,

            json=payload,

            timeout=30

        )

    except Exception as error:

        return jsonify({

            "status": "error",

            "message": (
                "Could not connect to Flutterwave."
            ),

            "details": str(error)

        }), 500


    # -----------------------------------------------------
    # READ FLUTTERWAVE RESPONSE
    # -----------------------------------------------------

    try:

        result = response.json()

    except Exception:

        result = {

            "raw_response":
                response.text

        }


    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    if (
        response.ok
        and result.get("status") == "success"
    ):

        payment_url = (
            result
            .get("data", {})
            .get("link")
        )


        if payment_url:

            return jsonify({

                "status": "success",

                "payment_url": payment_url,

                "tx_ref": tx_ref,

                "currency": currency,

                "amount": amount

            })


    # -----------------------------------------------------
    # FLUTTERWAVE ERROR
    # -----------------------------------------------------

    return jsonify({

        "status": "error",

        "message": (
            "Flutterwave could not create "
            "the hosted payment."
        ),

        "http_status": response.status_code,

        "flutterwave_response": result

    }), 400


# =========================================================
# PAYMENT CALLBACK
# =========================================================

@app.route("/payment-callback", methods=["GET"])
def payment_callback():

    status = request.args.get("status")

    tx_ref = request.args.get("tx_ref")

    transaction_id = request.args.get(
        "transaction_id"
    )


    # -----------------------------------------------------
    # No transaction ID
    # -----------------------------------------------------

    if not transaction_id:

        return redirect(FAILED_URL)


    # -----------------------------------------------------
    # Payment wasn't successful
    # -----------------------------------------------------

    if status != "successful":

        return redirect(
            FAILED_URL
            + "?tx_ref="
            + str(tx_ref or "")
        )


    # -----------------------------------------------------
    # Verify transaction server-side
    # -----------------------------------------------------

    if not FLW_SECRET_KEY:

        return redirect(FAILED_URL)


    verify_url = (
        FLW_VERIFY_URL
        + "/"
        + str(transaction_id)
        + "/verify"
    )


    headers = {

        "Authorization": (
            "Bearer "
            + FLW_SECRET_KEY
        ),

        "Content-Type": "application/json"

    }


    try:

        response = requests.get(

            verify_url,

            headers=headers,

            timeout=30

        )

        result = response.json()

    except Exception:

        return redirect(FAILED_URL)


    # -----------------------------------------------------
    # Extract transaction
    # -----------------------------------------------------

    transaction = result.get(
        "data",
        {}
    )


    transaction_status = transaction.get(
        "status"
    )


    transaction_currency = str(
        transaction.get(
            "currency",
            ""
        )
    ).upper()


    transaction_amount = float(
        transaction.get(
            "amount",
            0
        ) or 0
    )


    # -----------------------------------------------------
    # EXPECTED AMOUNT
    # -----------------------------------------------------

    if transaction_currency == "NGN":

        expected_amount = 100

        # AFTER TESTING CHANGE TO:
        # expected_amount = 19999


    elif transaction_currency == "USD":

        expected_amount = 14.99


    else:

        return redirect(FAILED_URL)


    # -----------------------------------------------------
    # VERIFY EVERYTHING
    # -----------------------------------------------------

    amount_is_correct = (
        transaction_amount
        >= expected_amount
    )


    status_is_correct = (
        transaction_status
        == "successful"
    )


    reference_is_correct = (
        tx_ref
        and transaction.get("tx_ref") == tx_ref
    )


    # -----------------------------------------------------
    # PAYMENT SUCCESSFUL
    # -----------------------------------------------------

    if (
        status_is_correct
        and amount_is_correct
        and reference_is_correct
    ):

        return redirect(

            SUCCESS_URL
            + "?tx_ref="
            + str(tx_ref)
            + "&transaction_id="
            + str(transaction_id)

        )


    # -----------------------------------------------------
    # PAYMENT FAILED / INVALID
    # -----------------------------------------------------

    return redirect(

        FAILED_URL
        + "?tx_ref="
        + str(tx_ref or "")

    )


# =========================================================
# PAYMENT STATUS
# =========================================================

@app.route("/payment-status", methods=["GET"])
def payment_status():

    tx_ref = request.args.get("tx_ref")


    if not tx_ref:

        return jsonify({

            "status": "error",

            "message": (
                "tx_ref is required."
            )

        }), 400


    return jsonify({

        "status": "pending",

        "tx_ref": tx_ref,

        "message": (
            "Transaction status endpoint "
            "is available."
        )

    })


# =========================================================
# SERVER
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )


    app.run(

        host="0.0.0.0",

        port=port

    )
