import os
import uuid
import requests

from flask import Flask, request, jsonify, redirect

app = Flask(__name__)

FLW_SECRET_KEY = os.environ.get("FLW_SECRET_KEY")

FLW_BASE_URL = "https://api.flutterwave.com/v3"


@app.route("/")
def home():
    return "PromptPro Hub Payment Server is running."


@app.route("/create-payment", methods=["POST"])
def create_payment():

    if not FLW_SECRET_KEY:
        return jsonify({
            "error": "Flutterwave secret key is not configured."
        }), 500

    data = request.get_json(silent=True) or {}

    currency = data.get("currency", "NGN")

    if currency == "NGN":
        amount = 100
    elif currency == "USD":
        amount = 19.99
    else:
        return jsonify({
            "error": "Unsupported currency."
        }), 400

    tx_ref = "PROMPTPRO-" + str(uuid.uuid4())

    payload = {
        "tx_ref": tx_ref,
        "amount": amount,
        "currency": currency,
        "redirect_url": "https://nyonggodspower726-wq.github.io/promptprohub/payment-callback.html",
        "customer": {
            "email": data.get(
                "email",
                "customer@promptprohub.com"
            )
        },
        "customizations": {
            "title": "PromptPro Hub",
            "description": "The Ultimate AI Business Toolkit"
        }
    }

    headers = {
        "Authorization": f"Bearer {FLW_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{FLW_BASE_URL}/payments",
        json=payload,
        headers=headers,
        timeout=30
    )

    result = response.json()

    if response.ok and result.get("status") == "success":

        return jsonify({
            "status": "success",
            "link": result["data"]["link"]
        })

    return jsonify({
        "status": "error",
        "flutterwave": result
    }), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
