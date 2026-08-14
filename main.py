import os
import requests

from flask import Flask, request, jsonify, redirect

app = Flask(__name__)

# =========================================================
# FLUTTERWAVE
# =========================================================

FLW_SECRET_KEY = os.environ.get("FLW_SECRET_KEY")
FLW_WEBHOOK_SECRET = os.environ.get("FLW_WEBHOOK_SECRET")

FLW_VERIFY_URL = "https://api.flutterwave.com/v3/transactions"


# =========================================================
# YOUR EXISTING FLUTTERWAVE PAYMENT LINKS
# =========================================================

USD_PAYMENT_LINK = "https://flutterwave.com/pay/mcwzznhuu0lo"

NGN_PAYMENT_LINK = "https://flutterwave.com/pay/fola86ilb2da"


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

PRODUCT_NAME = (
    "PromptPro Hub - The Ultimate AI Business Toolkit"
)


# =========================================================
# PRICES
# =========================================================

NGN_TEST_AMOUNT = 100

# After the ₦100 test works, change 100 to 19999.
NGN_FINAL_AMOUNT = 19999

USD_AMOUNT = 14.99


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
        "message": (
            "PromptPro Hub automatic payment "
            "server is running."
        ),
        "payment_system": (
            "Flutterwave Payment Links + Webhook"
        )
    })


# =========================================================
# CREATE PAYMENT
#
# IMPORTANT:
# We are NOT creating a new Flutterwave payment here.
#
# We simply return the payment link you already created
# in your Flutterwave dashboard.
# =========================================================

@app.route("/create-payment", methods=["POST"])
def create_payment():

    data = request.get_json(silent=True) or {}

    currency = str(
        data.get("currency", "NGN")
    ).upper()


    # -----------------------------------------------------
    # NAIRA
    # -----------------------------------------------------

    if currency == "NGN":

        return jsonify({
            "status": "success",
            "payment_url": NGN_PAYMENT_LINK,
            "currency": "NGN",
            "amount": NGN_TEST_AMOUNT
        })


    # -----------------------------------------------------
    # USD
    # -----------------------------------------------------

    if currency == "USD":

        return jsonify({
            "status": "success",
            "payment_url": USD_PAYMENT_LINK,
            "currency": "USD",
            "amount": USD_AMOUNT
        })


    # -----------------------------------------------------
    # INVALID CURRENCY
    # -----------------------------------------------------

    return jsonify({
        "status": "error",
        "message": (
            "Only NGN and USD payments are supported."
        )
    }), 400


# =========================================================
# PAYMENT CALLBACK
#
# This handles customers returning from a Flutterwave
# Standard payment flow.
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

        return redirect(
            FAILED_URL
        )


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
    # Verify payment
    # -----------------------------------------------------

    verified = verify_transaction(
        transaction_id
    )


    if not verified:

        return redirect(
            FAILED_URL
            + "?tx_ref="
            + str(tx_ref or "")
        )


    transaction = verified


    # -----------------------------------------------------
    # Check transaction
    # -----------------------------------------------------

    if not payment_is_valid(
        transaction,
        tx_ref
    ):

        return redirect(
            FAILED_URL
            + "?tx_ref="
            + str(tx_ref or "")
        )


    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    return redirect(
        SUCCESS_URL
        + "?tx_ref="
        + str(tx_ref)
        + "&transaction_id="
        + str(transaction_id)
    )


# =========================================================
# FLUTTERWAVE WEBHOOK
#
# Flutterwave sends POST notifications here after payment.
# =========================================================

@app.route(
    "/flutterwave-webhook",
    methods=["POST"]
)
def flutterwave_webhook():

    # -----------------------------------------------------
    # Verify webhook secret hash
    #
    # Your dashboard is currently configured under
    # V3 Live Webhooks, so Flutterwave sends the secret
    # hash in the "verif-hash" header.
    # -----------------------------------------------------

    incoming_hash = request.headers.get(
        "verif-hash"
    )


    if not FLW_WEBHOOK_SECRET:

        print(
            "ERROR: FLW_WEBHOOK_SECRET "
            "is not configured."
        )

        return jsonify({
            "status": "error"
        }), 500


    if (
        not incoming_hash
        or incoming_hash != FLW_WEBHOOK_SECRET
    ):

        print(
            "Rejected webhook: invalid secret hash."
        )

        return jsonify({
            "status": "error",
            "message": "Invalid webhook signature."
        }), 401


    # -----------------------------------------------------
    # Read webhook payload
    # -----------------------------------------------------

    payload = request.get_json(
        silent=True
    ) or {}


    print(
        "Flutterwave webhook received:"
    )

    print(payload)


    # -----------------------------------------------------
    # Get event
    # -----------------------------------------------------

    event = payload.get(
        "event"
    )


    # -----------------------------------------------------
    # We care about completed charges
    # -----------------------------------------------------

    if event != "charge.completed":

        return jsonify({
            "status": "received",
            "message": (
                "Event received but no payment "
                "processing was required."
            )
        }), 200


    # -----------------------------------------------------
    # Transaction data
    # -----------------------------------------------------

    transaction = payload.get(
        "data",
        {}
    )


    transaction_id = transaction.get(
        "id"
    )

    tx_ref = transaction.get(
        "tx_ref"
    )

    transaction_status = str(
        transaction.get(
            "status",
            ""
        )
    ).lower()


    # -----------------------------------------------------
    # Ignore unsuccessful transactions
    # -----------------------------------------------------

    if transaction_status != "successful":

        print(
            "Webhook payment was not successful."
        )

        return jsonify({
            "status": "received"
        }), 200


    # -----------------------------------------------------
    # Verify transaction directly with Flutterwave
    # -----------------------------------------------------

    if not transaction_id:

        print(
            "Webhook did not contain transaction ID."
        )

        return jsonify({
            "status": "received"
        }), 200


    verified = verify_transaction(
        transaction_id
    )


    if not verified:

        print(
            "Transaction verification failed."
        )

        return jsonify({
            "status": "received"
        }), 200


    # -----------------------------------------------------
    # Validate payment
    # -----------------------------------------------------

    if not payment_is_valid(
        verified,
        tx_ref
    ):

        print(
            "Webhook payment failed validation."
        )

        return jsonify({
            "status": "received"
        }), 200


    # -----------------------------------------------------
    # CUSTOMER INFORMATION
    # -----------------------------------------------------

    customer = verified.get(
        "customer",
        {}
    )


    customer_email = customer.get(
        "email"
    )

    customer_name = customer.get(
        "name",
        "PromptPro Hub Customer"
    )


    print(
        "VALID PAYMENT RECEIVED"
    )

    print(
        "Customer:",
        customer_name
    )

    print(
        "Email:",
        customer_email
    )

    print(
        "Transaction:",
        transaction_id
    )

    print(
        "Reference:",
        tx_ref
    )


    # -----------------------------------------------------
    # IMPORTANT
    #
    # We are NOT sending the ebook email yet.
    #
    # First we confirm that the webhook + payment
    # verification works correctly.
    #
    # The next step will connect the email delivery.
    # -----------------------------------------------------

    return jsonify({
        "status": "success",
        "message": (
            "Payment received and verified."
        ),
        "transaction_id": transaction_id,
        "tx_ref": tx_ref,
        "customer_email": customer_email
    }), 200


# =========================================================
# VERIFY TRANSACTION
# =========================================================

def verify_transaction(transaction_id):

    if not FLW_SECRET_KEY:

        print(
            "ERROR: FLW_SECRET_KEY is missing."
        )

        return None


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

        "Content-Type":
            "application/json"

    }


    try:

        response = requests.get(

            verify_url,

            headers=headers,

            timeout=30

        )


        result = response.json()


    except Exception as error:

        print(
            "Verification error:",
            error
        )

        return None


    if not response.ok:

        print(
            "Flutterwave verification failed:"
        )

        print(result)

        return None


    if result.get("status") != "success":

        print(
            "Flutterwave returned unsuccessful "
            "verification:"
        )

        print(result)

        return None


    return result.get(
        "data",
        {}
    )


# =========================================================
# VALIDATE PAYMENT
# =========================================================

def payment_is_valid(
    transaction,
    tx_ref=None
):

    transaction_status = str(
        transaction.get(
            "status",
            ""
        )
    ).lower()


    currency = str(
        transaction.get(
            "currency",
            ""
        )
    ).upper()


    amount = float(
        transaction.get(
            "amount",
            0
        ) or 0
    )


    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    if transaction_status != "successful":

        print(
            "Invalid transaction status:",
            transaction_status
        )

        return False


    # -----------------------------------------------------
    # Currency + expected amount
    # -----------------------------------------------------

    if currency == "NGN":

        expected_amount = NGN_TEST_AMOUNT


    elif currency == "USD":

        expected_amount = USD_AMOUNT


    else:

        print(
            "Unsupported currency:",
            currency
        )

        return False


    # -----------------------------------------------------
    # Amount
    # -----------------------------------------------------

    if amount < expected_amount:

        print(
            "Incorrect payment amount.",
            "Received:",
            amount,
            "Expected:",
            expected_amount
        )

        return False


    # -----------------------------------------------------
    # Reference
    #
    # Only compare when a reference was supplied.
    # -----------------------------------------------------

    if tx_ref:

        returned_reference = transaction.get(
            "tx_ref"
        )

        if returned_reference != tx_ref:

            print(
                "Transaction reference mismatch."
            )

            return False


    return True


# =========================================================
# PAYMENT STATUS
# =========================================================

@app.route(
    "/payment-status",
    methods=["GET"]
)
def payment_status():

    tx_ref = request.args.get(
        "tx_ref"
    )


    if not tx_ref:

        return jsonify({

            "status": "error",

            "message":
                "tx_ref is required."

        }), 400


    return jsonify({

        "status": "pending",

        "tx_ref": tx_ref,

        "message":
            "Transaction status endpoint "
            "is available."

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
