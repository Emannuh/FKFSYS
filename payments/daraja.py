import base64
import logging
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class MpesaDarajaAPI:
    def __init__(self):
        self.consumer_key  = os.getenv('MPESA_CONSUMER_KEY')
        self.consumer_secret = os.getenv('MPESA_CONSUMER_SECRET')
        self.shortcode     = os.getenv('MPESA_SHORTCODE')
        self.passkey       = os.getenv('MPESA_PASSKEY')
        self.callback_url  = os.getenv('MPESA_CALLBACK_URL')
        self.environment   = os.getenv('MPESA_ENVIRONMENT', 'sandbox')

        self.base_url = (
            "https://api.safaricom.co.ke"
            if self.environment == 'production'
            else "https://sandbox.safaricom.co.ke"
        )

    def get_access_token(self):
        """Get OAuth access token from Daraja API."""
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        auth_string  = f"{self.consumer_key}:{self.consumer_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        try:
            response = requests.get(url, headers={"Authorization": f"Basic {encoded_auth}"})
            response.raise_for_status()
            return response.json()['access_token']
        except Exception as exc:
            logger.error("M-Pesa: failed to get access token: %s", exc)
            return None

    def lipa_na_mpesa_online(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK Push payment."""
        access_token = self.get_access_token()
        if not access_token:
            logger.error("M-Pesa: cannot initiate payment — no access token")
            return None

        # Normalise phone number to 254XXXXXXXXX
        phone = (
            str(phone_number)
            .replace('+', '').replace(' ', '').replace('-', '')
        )
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif not phone.startswith('254'):
            phone = '254' + phone

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password  = base64.b64encode(
            f"{self.shortcode}{self.passkey}{timestamp}".encode()
        ).decode()

        payload = {
            "BusinessShortCode": int(self.shortcode),
            "Password":          password,
            "Timestamp":         timestamp,
            "TransactionType":   "CustomerPayBillOnline",
            "Amount":            int(amount),
            "PartyA":            int(phone),
            "PartyB":            int(self.shortcode),
            "PhoneNumber":       int(phone),
            "CallBackURL":       self.callback_url,
            "AccountReference":  str(account_reference)[:12],
            "TransactionDesc":   str(transaction_desc)[:13],
        }

        logger.info("M-Pesa STK Push → %s, KSh %s", phone, amount)
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as exc:
            logger.error("M-Pesa HTTP error: %s — %s", exc, getattr(exc.response, 'text', ''))
            return None
        except Exception as exc:
            logger.error("M-Pesa payment error: %s", exc)
            return None

    def check_transaction_status(self, checkout_request_id):
        """Check status of an STK Push transaction."""
        access_token = self.get_access_token()
        if not access_token:
            return None

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password  = base64.b64encode(
            f"{self.shortcode}{self.passkey}{timestamp}".encode()
        ).decode()

        try:
            response = requests.post(
                f"{self.base_url}/mpesa/stkpushquery/v1/query",
                json={
                    "BusinessShortCode": self.shortcode,
                    "Password":          password,
                    "Timestamp":         timestamp,
                    "CheckoutRequestID": checkout_request_id,
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("M-Pesa status check error: %s", exc)
            return None
