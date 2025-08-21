# api/index.py
from flask import Flask, request, jsonify
import os
import base64
import requests
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

app = Flask(__name__)

# --- Load secrets from environment variables ---
PRIVATE_KEY_PEM = os.environ.get("PRIVATE_KEY_PEM")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_NAME = "Ankard Support"

if PRIVATE_KEY_PEM:
    private_key = serialization.load_pem_private_key(
        PRIVATE_KEY_PEM.encode(),
        password=None,
    )
else:
    private_key = None

def create_license(data_to_sign):
    if not private_key:
        raise ValueError("Private key is not loaded.")
    message = data_to_sign.encode('utf-8')
    signature = private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )
    return f"{data_to_sign}::{base64.b64encode(signature).decode('utf-8')}"

def send_license_email(recipient_email, license_key):
    if not BREVO_API_KEY or not SENDER_EMAIL:
        print("ERROR: BREVO_API_KEY or SENDER_EMAIL is not set.")
        return False
    
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"api-key": BREVO_API_KEY, "Content-Type": "application/json"}
    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": recipient_email}],
        "subject": "Your Ankard PRO License Key",
        "htmlContent": f"""
            <html><body>
                <h1>Thank you for purchasing Ankard PRO!</h1>
                <p>Your license key is ready. Please copy this key and paste it into the activation window in the Ankard app.</p>
                <p style="background-color:#f0f0f0; padding:15px; border-radius:5px; font-family:monospace; font-size:16px;">
                    {license_key}
                </p>
                <p>If you have any questions, please reply to this email.</p>
                <p>— The Ankard Team</p>
            </body></html>
        """
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"Successfully sent email to {recipient_email} via Brevo.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to send email via Brevo. {e.response.text if e.response else e}")
        return False

# Vercel will make this available at yourdomain.com/api/webhook-listener
@app.route('/webhook-listener', methods=['POST'])
def handle_webhook():
    data = request.get_json()
    if not data or 'customer_email' not in data:
        return jsonify({"status": "error", "message": "Missing customer_email"}), 400

    customer_email = data.get('customer_email')
    
    try:
        license_key = create_license(customer_email)
        if send_license_email(customer_email, license_key):
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Failed to send email."}), 500
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to process webhook. Error: {e}")
        return jsonify({"status": "error", "message": "Internal server error."}), 500