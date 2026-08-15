import os
import time
import hmac
import hashlib
import base64
import uuid
import requests
from flask import Flask, request, jsonify, redirect
app = Flask(__name__)
FLW_CLIENT_ID = os.environ.get("FLW_CLIENT_ID")
FLW_CLIENT_SECRET = os.environ.get("FLW_CLIENT_SECRET")
FLW_WEBHOOK_SECRET = os.environ.get("FLW_WEBHOOK_SECRET")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.environ.get(
    "RESEND_FROM_EMAIL",
    "PromptPro Hub <onboarding@resend.dev>"
)
EBOOK_DOWNLOAD_URL = os.environ.get(
    "EBOOK_DOWNLOAD_URL",
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/download.html"
)
PORT = int(os.environ.get("PORT", "8080"))
FLW_TOKEN_URL = (
    "https://idp.flutterwave.com/"
    "realms/flutterwave/protocol/openid-connect/token"
)
FLW_API_BASE_URL = os.environ.get(
    "FLW_API_BASE_URL",
    "https://f4bexperience.flutterwave.com"
).rstrip("/")
USD_PAYMENT_LINK = (
    "https://flutterwave.com/pay/mcwzznhuu0lo"
)
NGN_PAYMENT_LINK = (
    "https://flutterwave.com/pay/fola86ilb2da"
)
SUCCESS_URL = (
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/download.html"
)
FAILED_URL = (
    "https://nyonggodspower726-wq.github.io/"
    "promptprohub/payment-failed.html"
)
PRODUCT_NAME = (
    "PromptPro Hub - The Ultimate AI Business Toolkit"
)
NGN_EXPECTED_AMOUNT = 100
USD_EXPECTED_AMOUNT = 14.99
_access_token = None
_token_expires_at = 0
def get_access_token():
    """
    Obtain a fresh Flutterwave V4 OAuth token automatically.

    The token is temporary. We do NOT manually maintain it.
    When it is close to expiry, this function gets another one
    using the permanent Client ID + Client Secret.
    """

    global _access_token
    global _token_expires_at

    # Reuse current token while it has >60 seconds remaining.
    if (
        _access_token
        and time.time() < (_token_expires_at - 60)
    ):
        return _access_token

    if not FLW_CLIENT_ID:
        raise RuntimeError(
            "FLW_CLIENT_ID is missing in Railway Variables."
        )

    if not FLW_CLIENT_SECRET:
        raise RuntimeError(
            "FLW_CLIENT_SECRET is missing in Railway Variables."
        )

    response = requests.post(
        FLW_TOKEN_URL,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },
        data={
            "client_id": FLW_CLIENT_ID,
            "client_secret": FLW_CLIENT_SECRET,
            "grant_type": "client_credentials"
        },
        timeout=30
    )

    try:
        result = response.json()
    except Exception:
        result = {
            "raw_response": response.text
        }

    if (
        not response.ok
        or not result.get("access_token")
    ):
        raise RuntimeError(
            "Flutterwave V4 authentication failed: "
            + str(result)
        )

    _access_token = result["access_token"]

    expires_in = int(
        result.get("expires_in", 600)
    )

    _token_expires_at = (
        time.time() + expires_in
    )

    print(
        "V4 OAuth token obtained. "
        f"expires_in={expires_in}s"
    )

    return _access_token


# =========================================================
# FLUTTERWAVE V4 WEBHOOK SIGNATURE
# =========================================================

def verify_flutterwave_signature(
    raw_body,
    incoming_signature
):
    """
    Flutterwave V4 signs the raw webhook body with
    HMAC-SHA256 using the webhook secret hash and returns
    the Base64 digest in the flutterwave-signature header.
    """

    if not FLW_WEBHOOK_SECRET:
        print(
            "ERROR: FLW_WEBHOOK_SECRET is missing."
        )
        return False

    if not incoming_signature:
        print(
            "ERROR: flutterwave-signature header is missing."
        )
        return False

    expected_digest = hmac.new(
        FLW_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).digest()

    expected_signature = base64.b64encode(
        expected_digest
    ).decode("utf-8")

    return hmac.compare_digest(
        expected_signature,
        incoming_signature
    )


# =========================================================
# VERIFY V4 CHARGE
# =========================================================

def verify_charge(charge_id):
    """
    Fetch the charge from Flutterwave V4 using a fresh
    OAuth access token.

    V4 charge IDs look like chg_...
    """

    if not charge_id:
        return None

    try:
        token = get_access_token()
    except Exception as error:
        print(
            "Could not obtain V4 access token:",
            error
        )
        return None

    url = (
        FLW_API_BASE_URL
        + "/charges/"
        + str(charge_id)
    )

    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Trace-Id": str(uuid.uuid4())
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )
    except Exception as error:
        print(
            "Flutterwave V4 charge request failed:",
            error
        )
        return None

    try:
        result = response.json()
    except Exception:
        print(
            "Flutterwave returned non-JSON:",
            response.text
        )
        return None

    if not response.ok:
        print(
            "V4 charge verification HTTP error:",
            response.status_code,
            result
        )
        return None

    if result.get("status") != "success":
        print(
            "V4 charge verification unsuccessful:",
            result
        )
        return None

    return result.get("data") or {}


# =========================================================
# VALIDATE PAYMENT
# =========================================================

def payment_is_valid(transaction):
    """
    Never send the product just because a webhook arrived.

    We check:
      - successful/succeeded status
      - currency
      - minimum expected amount
    """

    status = str(
        transaction.get("status", "")
    ).lower()

    currency = str(
        transaction.get("currency", "")
    ).upper()

    try:
        amount = float(
            transaction.get("amount", 0) or 0
        )
    except Exception:
        amount = 0.0

    if status not in (
        "succeeded",
        "successful"
    ):
        print(
            "Payment not successful:",
            status
        )
        return False

    if currency == "NGN":
        expected_amount = NGN_EXPECTED_AMOUNT

    elif currency == "USD":
        expected_amount = USD_EXPECTED_AMOUNT

    else:
        print(
            "Unsupported currency:",
            currency
        )
        return False

    if amount < expected_amount:
        print(
            "Payment amount too low.",
            "received=", amount,
            "expected=", expected_amount
        )
        return False

    return True


# =========================================================
# RESEND
# =========================================================

def send_ebook_email(
    email,
    customer_name,
    charge_id,
    currency,
    amount
):
    """
    Sends the customer an email containing the existing
    PromptPro Hub download.html page.
    """

    if not RESEND_API_KEY:
        raise RuntimeError(
            "RESEND_API_KEY is missing in Railway Variables."
        )

    if not email:
        raise RuntimeError(
            "Customer email is missing."
        )

    name = customer_name or "Customer"

    subject = (
        "Your PromptPro Hub AI Business Toolkit is ready 🎉"
    )

    html = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#0B1220;
font-family:Arial,sans-serif;color:#ffffff;">
<div style="max-width:600px;margin:30px auto;
background:#111C33;padding:35px;border-radius:16px;">
<h1 style="color:#4F8CFF;">
Payment Successful 🎉
</h1>
<p style="font-size:17px;line-height:1.7;">
Hello {name},
</p>
<p style="font-size:17px;line-height:1.7;">
Thank you for purchasing
<strong>{PRODUCT_NAME}</strong>.
</p>
<p style="font-size:17px;line-height:1.7;">
Your payment of
<strong>{amount} {currency}</strong>
has been successfully received.
</p>
<p style="font-size:17px;line-height:1.7;">
Your ebook is ready. You can access the download page
using the button below.
</p>
<div style="text-align:center;margin:35px 0;">
<a href="{EBOOK_DOWNLOAD_URL}"
style="display:inline-block;background:#4F8CFF;
color:#ffffff;text-decoration:none;padding:16px 30px;
border-radius:10px;font-size:17px;font-weight:bold;">
📥 Download Your Ebook
</a>
</div>
<p style="font-size:14px;color:#b7c4df;line-height:1.7;">
If you closed the payment page, don't worry.
This email gives you another way to access your purchase.
</p>
<p style="font-size:13px;color:#8090ad;">
Payment reference: {charge_id}
</p>
<p style="font-size:14px;color:#9fb0d3;">
PromptPro Hub Support
</p>
</div>
</body>
</html>
"""

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization":
                "Bearer " + RESEND_API_KEY,
            "Content-Type":
                "application/json",
            "User-Agent":
                "PromptProHub-Railway/1.0"
        },
        json={
            "from": RESEND_FROM_EMAIL,
            "to": [email],
            "subject": subject,
            "html": html,
            "text": (
                "Payment successful.\n\n"
                "Access your PromptPro Hub ebook here:\n"
                + EBOOK_DOWNLOAD_URL
            )
        },
        timeout=30
    )

    try:
        result = response.json()
    except Exception:
        result = {
            "raw_response": response.text
        }

    if not response.ok:
        raise RuntimeError(
            "Resend API failed: "
            + str(result)
        )

    print(
        "Resend accepted ebook email:",
        result
    )

    return result


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
# HEALTH CHECK
# =========================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "success",
        "message": (
            "PromptPro Hub V4 webhook/email server "
            "is running."
        ),
        "payment_links": "existing Flutterwave links",
        "email_provider": "Resend",
        "download_page": EBOOK_DOWNLOAD_URL
    })


# =========================================================
# CREATE PAYMENT
#
# Existing Flutterwave payment links only.
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
        data.get("currency", "NGN")
    ).upper()

    if currency == "NGN":

        return jsonify({
            "status": "success",
            "payment_url": NGN_PAYMENT_LINK,
            "currency": "NGN",
            "amount": NGN_EXPECTED_AMOUNT
        })

    if currency == "USD":

        return jsonify({
            "status": "success",
            "payment_url": USD_PAYMENT_LINK,
            "currency": "USD",
            "amount": USD_EXPECTED_AMOUNT
        })

    return jsonify({
        "status": "error",
        "message": (
            "Only NGN and USD payments are supported."
        )
    }), 400


# =========================================================
# CUSTOMER REDIRECT
# =========================================================

@app.route(
    "/payment-callback",
    methods=["GET"]
)
def payment_callback():

    status = str(
        request.args.get(
            "status",
            ""
        )
    ).lower()

    if status in (
        "successful",
        "success"
    ):
        return redirect(
            SUCCESS_URL
        )

    return redirect(
        FAILED_URL
    )


# =========================================================
# FLUTTERWAVE V4 WEBHOOK
# =========================================================

@app.route(
    "/flutterwave-webhook",
    methods=["POST"]
)
def flutterwave_webhook():

    # IMPORTANT:
    # Read raw bytes BEFORE parsing JSON.
    raw_body = request.get_data(
        cache=True
    )

    signature = request.headers.get(
        "flutterwave-signature"
    )

    # -----------------------------------------------------
    # 1. Authenticate Flutterwave webhook
    # -----------------------------------------------------

    if not verify_flutterwave_signature(
        raw_body,
        signature
    ):
        print(
            "Rejected webhook: invalid signature."
        )

        return jsonify({
            "status": "error",
            "message": "Invalid webhook signature."
        }), 401

    # -----------------------------------------------------
    # 2. Parse payload
    # -----------------------------------------------------

    payload = (
        request.get_json(
            silent=True
        )
        or {}
    )

    print(
        "Flutterwave V4 webhook received:",
        payload
    )

    event_type = (
        payload.get("type")
        or payload.get("event")
    )

    # -----------------------------------------------------
    # 3. We only need completed charges
    # -----------------------------------------------------

    if event_type != "charge.completed":

        return jsonify({
            "status": "received",
            "message": "Event received."
        }), 200

    webhook_data = (
        payload.get("data")
        or {}
    )

    charge_id = webhook_data.get(
        "id"
    )

    if not charge_id:

        print(
            "charge.completed webhook had no data.id."
        )

        return jsonify({
            "status": "received"
        }), 200

    # -----------------------------------------------------
    # 4. Verify the charge directly with Flutterwave V4
    # -----------------------------------------------------

    verified = verify_charge(
        charge_id
    )

    if not verified:

        print(
            "Payment webhook received, but V4 "
            "charge verification failed."
        )

        # Return 200 so the endpoint itself is healthy.
        # The log tells us exactly where the failure is.
        return jsonify({
            "status": "received",
            "message": "Charge verification failed."
        }), 200

    # -----------------------------------------------------
    # 5. Validate status, amount and currency
    # -----------------------------------------------------

    if not payment_is_valid(
        verified
    ):

        print(
            "Payment failed validation."
        )

        return jsonify({
            "status": "received",
            "message": "Payment validation failed."
        }), 200

    # -----------------------------------------------------
    # 6. Get customer
    # -----------------------------------------------------

    customer = (
        verified.get("customer")
        or webhook_data.get("customer")
        or {}
    )

    # V4 can represent customer information in different
    # shapes. Handle both a dictionary and a string ID.
    if isinstance(customer, dict):

        customer_email = customer.get(
            "email"
        )

        customer_name = customer.get(
            "name"
        )

        if isinstance(
            customer_name,
            dict
        ):
            customer_name = " ".join(
                str(value)
                for value in [
                    customer_name.get("first"),
                    customer_name.get("middle"),
                    customer_name.get("last")
                ]
                if value
            )

    else:

        customer_email = webhook_data.get(
            "customer_email"
        )

        customer_name = (
            webhook_data.get("customer_name")
            or "PromptPro Hub Customer"
        )

    if not customer_email:

        print(
            "Verified payment has no customer email."
        )

        return jsonify({
            "status": "received",
            "message": (
                "Payment verified but "
                "customer email was unavailable."
            )
        }), 200

    currency = str(
        verified.get(
            "currency",
            webhook_data.get(
                "currency",
                ""
            )
        )
    ).upper()

    amount = verified.get(
        "amount",
        webhook_data.get(
            "amount",
            0
        )
    )

    # -----------------------------------------------------
    # 7. Send the ebook email
    # -----------------------------------------------------

    try:

        email_result = send_ebook_email(
            email=customer_email,
            customer_name=customer_name,
            charge_id=charge_id,
            currency=currency,
            amount=amount
        )

    except Exception as error:

        print(
            "RESEND ERROR:",
            error
        )

        return jsonify({
            "status": "received",
            "message": (
                "Payment verified, but email "
                "delivery failed."
            ),
            "error": str(error)
        }), 200

    # -----------------------------------------------------
    # 8. Finished
    # -----------------------------------------------------

    return jsonify({
        "status": "success",
        "message": (
            "Payment verified and ebook email sent."
        ),
        "charge_id": charge_id,
        "customer_email": customer_email,
        "resend": email_result
    }), 200


# =========================================================
# SIMPLE TEST EMAIL ENDPOINT
#
# This lets you test Resend WITHOUT making another payment.
#
# Open:
# /test-email?email=YOUR_EMAIL
#
# IMPORTANT:
# Only use this while testing. Remove or protect this route
# before launching publicly.
# =========================================================

@app.route(
    "/test-email",
    methods=["GET"]
)
def test_email():

    email = request.args.get(
        "email"
    )

    if not email:

        return jsonify({
            "status": "error",
            "message": (
                "Use /test-email?email=your@email.com"
            )
        }), 400

    try:

        result = send_ebook_email(
            email=email,
            customer_name="PromptPro Hub Test Customer",
            charge_id="TEST-EMAIL",
            currency="NGN",
            amount=NGN_EXPECTED_AMOUNT
        )

        return jsonify({
            "status": "success",
            "message": "Test email submitted to Resend.",
            "resend": result
        })

    except Exception as error:

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500


# =========================================================
# SERVER
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=PORT
)
