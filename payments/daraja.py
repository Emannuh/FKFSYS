import base64
import requests
import json
from datetime import datetime
from django.conf import settings
import os
from dotenv import load_dotenv

load_dotenv()

class MpesaDarajaAPI:
    def __init__(self):
        self.consumer_key = os.getenv('MPESA_CONSUMER_KEY')
        self.consumer_secret = os.getenv('MPESA_CONSUMER_SECRET')
        self.shortcode = os.getenv('MPESA_SHORTCODE')
        self.passkey = os.getenv('MPESA_PASSKEY')
        self.callback_url = os.getenv('MPESA_CALLBACK_URL')
        self.environment = os.getenv('MPESA_ENVIRONMENT', 'sandbox')  # 'sandbox' or 'production'
        
        # Use appropriate base URL based on environment
        if self.environment == 'production':
            self.base_url = "https://api.safaricom.co.ke"  # Production
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"  # Sandbox
        
    def get_access_token(self):
        """Get OAuth access token from Daraja API"""
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        
        # Encode consumer key and secret
        auth_string = f"{self.consumer_key}:{self.consumer_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_auth}"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()['access_token']
        except Exception as e:
            print(f"Error getting access token: {e}")
            return None
    
    def lipa_na_mpesa_online(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK Push payment"""
        access_token = self.get_access_token()
        if not access_token:
            print("Failed to get access token")
            return None
        
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        
        # Clean and format phone number - remove +, spaces, dashes
        phone_number = str(phone_number).replace('+', '').replace(' ', '').replace('-', '')
        
        # Ensure phone starts with 254
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number
        
        # Generate timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Generate password
        password_string = f"{self.shortcode}{self.passkey}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()
        
        # Ensure amount is integer
        amount = int(amount)
        
        payload = {
            "BusinessShortCode": int(self.shortcode),
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": int(phone_number),
            "PartyB": int(self.shortcode),
            "PhoneNumber": int(phone_number),
            "CallBackURL": self.callback_url,
            "AccountReference": str(account_reference)[:12],  # Max 12 chars
            "TransactionDesc": str(transaction_desc)[:13]  # Max 13 chars
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            print(f"Sending STK Push to: {phone_number}")
            print(f"Amount: {amount}")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, json=payload, headers=headers)
            print(f"Response Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response content: {e.response.text if e.response else 'No response'}")
            return None
        except Exception as e:
            print(f"Error initiating payment: {e}")
            return None
    
    def check_transaction_status(self, checkout_request_id):
        """Check status of a transaction"""
        access_token = self.get_access_token()
        if not access_token:
            return None
        
        url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_string = f"{self.shortcode}{self.passkey}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()
        
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error checking transaction: {e}")
            return None