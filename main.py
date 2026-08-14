import os
import uuid
import time
import requests

from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================================================
# FLUTTERWAVE V4 CONFIGURATION
# =========================================================

FLW_CLIENT_ID = os.environ.get("FLW_CLIENT_ID")
FLW_CLIENT_SECRET = os.environ.get("FLW_CLIENT_SECRET")

# Flutterwave V4 Production API
FLW_API_URL = "https://f4bexperience.flutterwave.com"

# Flutterwave V4 OAuth endpoint
FLW_TOKEN_URL = (
    "https://idp.flutterwave.com/"
    "realms/flutterwave/protocol/openid-connect/token"
)

# GitHub Pages
SUCCESS_URL = (
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/success.html"
)

FAILED_URL = (
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/payment-failed.html"
)


# =========================================================
# ACCESS TOKEN CACHE
# =========================================================

access_token = None
token_expires_at = 0


def get_access_token():

    global access_token
    global token_expires_at

    # Reuse token while it has more than 60 seconds left.
    if (
        access_token
        and time.time() < token_expires_at - 60
    ):
        return access_token

    if not FLW_CLIENT_ID:
        raise Exception(
            "FLW_CLIENT_ID is not configured in Railway."
        )

    if not FLW_CLIENT_SECRET:
        raise Exception(
            "FLW_CLIENT_SECRET is not configured in Railway."
        )

    headers = {
        "Content-Type":
            "application/x-www-form-urlencoded"
    }

    data = {
        "client_id": FLW_CLIENT_ID,
        "client_secret": FLW_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }

    response = requests.post(
        FLW_TOKEN_URL,
        headers=headers,
        data=data,
        timeout=30
    )

    try:
        result = response.json()
    except Exception:
        raise Exception(
            "Flutterwave authentication returned "
            "an invalid response."
        )

    if (
        not response.ok
        or not result.get("access_token")
    ):
        raise Exception(
            "Flutterwave authentication failed: "
            + str(result)
        )

    access_token = result["access_token"]

    expires_in = int(
        result.get("expires_in", 600)
    )

    token_expires_at = (
        time.time() + expires_in
    )

    return access_token


# =========================================================
# CORS
# =========================================================

@app.after_request
def add_cors_headers(response):

    response.headers[
        "Access-Control-Allow-Origin"
    ] = "*"

    response.headers[
        "Access-Control-Allow-Headers"
    ] = "Content-Type"
    
    response.headers[
        "Access-Control-Allow-Methods"
    ] = "GET, POST, OPTIONS"

    return response


# =========================================================
# HOME / HEALTH CHECK
# =========================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "success",
        "message":
            "PromptPro Hub V4 payment server "
            "is running."
    })


# =========================================================
# TEST FLUTTERWAVE AUTHENTICATION
# =========================================================

@app.route("/test-flutterwave", methods=["GET"])
def test_flutterwave():

    try:

        token = get_access_token()

        return jsonify({
            "status": "success",
            "message":
                "Flutterwave V4 authentication "
                "is working.",
            "token_received": bool(token)
        })

    except Exception as error:

        return jsonify({
            "status": "error",
            "message":
                "Flutterwave V4 authentication failed.",
            "details": str(error)
        }), 500


# =========================================================
# CREATE PAYMENT
# =========================================================

@app.route(
    "/create-payment",
    methods=["POST"]
)
def create_payment():

    data = (
        request.get_json(silent=True)
        or {}
    )

    currency = str(
        data.get(
            "currency",
            "NGN"
        )
    ).upper()

    email = data.get(
        "email",
        "customer@promptprohub.com"
    )


    # =====================================================
    # PRICES
    # =====================================================

    if currency == "NGN":

        # REAL ₦100 TEST
        #
        # After successful testing:
        # change 100 to 19999.
        amount = 100

    elif currency == "USD":

        amount = 14.99

    else:

        return jsonify({
            "status": "error",
            "message":
                "Only NGN and USD payments "
                "are supported."
        }), 400


    # =====================================================
    # UNIQUE REFERENCE
    # =====================================================

    reference = (
        "PROMPTPRO-"
        + currency
        + "-"
        + uuid.uuid4().hex[:16]
    )


    # =====================================================
    # GET ACCESS TOKEN
    # =====================================================

    try:

        token = get_access_token()

    except Exception as error:

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500


    # =====================================================
    # V4 ORCHESTRATOR
    # =====================================================

    url = (
        FLW_API_URL
        + "/orchestration/direct-charges"
    )

    headers = {
        "Authorization":
            f"Bearer {token}",

        "Content-Type":
            "application/json",

        "X-Trace-Id":
            str(uuid.uuid4()),

        "X-Idempotency-Key":
            str(uuid.uuid4())
    }


    # =====================================================
    # CUSTOMER INFORMATION
    # =====================================================

    payload = {

        "amount": amount,

        "currency": currency,

        "reference": reference,

        "redirect_url": SUCCESS_URL,

        "customer": {
            "email": email
        },

        "payment_method": {
            "type": "card"
        }
    }


    # =====================================================
    # SEND PAYMENT REQUEST
    # =====================================================

    try:

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        try:
            result = response.json()
        except Exception:
            result = {
                "raw_response":
                    response.text
            }

    except Exception as error:

        return jsonify({
            "status": "error",
            "message":
                "Could not connect to "
                "Flutterwave.",
            "details": str(error)
        }), 500


    # =====================================================
    # GET FLUTTERWAVE REDIRECT URL
    # =====================================================

    if response.ok:

        flutter_data = result.get(
            "data",
            {}
        )

        next_action = flutter_data.get(
            "next_action",
            {}
        )

        redirect_data = next_action.get(
            "redirect_url",
            {}
        )


        # V4 returns:
        #
        # data
        #   └── next_action
        #        └── redirect_url
        #             └── url

        if isinstance(
            redirect_data,
            dict
        ):

            payment_url = redirect_data.get(
                "url"
            )

        else:

            payment_url = redirect_data


        if payment_url:

            return jsonify({

                "status": "success",

                "payment_url":
                    payment_url,

                "reference":
                    reference,

                "currency":
                    currency,

                "amount":
                    amount
            })


    # =====================================================
    # FLUTTERWAVE ERROR
    # =====================================================

    return jsonify({

        "status": "error",

        "message":
            "Flutterwave could not "
            "start the payment.",

        "http_status":
            response.status_code,

        "flutterwave_response":
            result

    }), 400


# =========================================================
# PAYMENT STATUS
# =========================================================

@app.route(
    "/payment-status",
    methods=["GET"]
)
def payment_status():

    reference = request.args.get(
        "reference"
    )

    if not reference:

        return jsonify({
            "status": "error",
            "message":
                "Payment reference is required."
        }), 400


    # We will complete the V4 verification
    # after confirming the exact charge response
    # from your live Flutterwave account.

    return jsonify({

        "status": "pending",

        "reference":
            reference,

        "message":
            "Payment verification endpoint "
            "is ready."
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
