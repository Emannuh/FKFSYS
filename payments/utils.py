import base64
import requests
import json
from datetime import datetime
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class DarajaAPI:
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        
        if settings.MPESA_ENVIRONMENT == 'sandbox':
            self.base_url = 'https://sandbox.safaricom.co.ke'
        else:
            self.base_url = 'https://api.safaricom.co.ke'
    
    def get_access_token(self):
        try:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            auth = (self.consumer_key, self.consumer_secret)
            headers = {'Content-Type': 'application/json'}
            
            response = requests.get(url, auth=auth, headers=headers)
            
            if response.status_code == 200:
                token_data = response.json()
                return token_data.get('access_token')
            else:
                logger.error(f"Failed to get access token: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            return None
    
    def generate_password(self, timestamp):
        data_to_encode = f"{self.shortcode}{self.passkey}{timestamp}"
        encoded = base64.b64encode(data_to_encode.encode()).decode()
        return encoded
    
    def stk_push(self, phone_number, amount, account_reference, transaction_desc, callback_url=None):
        try:
            access_token = self.get_access_token()
            if not access_token:
                return None, "Failed to get access token"
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            phone_number = phone_number.replace('+', '').replace(' ', '')
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif phone_number.startswith('254'):
                pass
            else:
                phone_number = '254' + phone_number
            
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": str(int(amount)),
                "PartyA": phone_number,
                "PartyB": self.shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": callback_url or settings.MPESA_CALLBACK_URL,
                "AccountReference": account_reference[:12],
                "TransactionDesc": transaction_desc[:13]
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                return result, "STK Push initiated successfully"
            else:
                logger.error(f"STK Push failed: {response.text}")
                return None, f"STK Push failed: {response.text}"
                
        except Exception as e:
            logger.error(f"Error in STK Push: {str(e)}")
            return None, f"Error: {str(e)}"
    
    def query_stk_status(self, checkout_request_id):
        try:
            access_token = self.get_access_token()
            if not access_token:
                return None, "Failed to get access token"
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                return response.json(), "Query successful"
            else:
                return None, f"Query failed: {response.text}"
                
        except Exception as e:
            return None, f"Error: {str(e)}"

def initiate_stk_push(phone_number, amount, account_reference, transaction_desc):
    daraja = DarajaAPI()
    return daraja.stk_push(phone_number, amount, account_reference, transaction_desc)

def query_stk_status(checkout_request_id):
    daraja = DarajaAPI()
    return daraja.query_stk_status(checkout_request_id)

def validate_mpesa_callback(data):
    required_fields = ['Body', 'Body.stkCallback', 'Body.stkCallback.CheckoutRequestID']
    
    for field in required_fields:
        keys = field.split('.')
        current = data
        for key in keys:
            if key in current:
                current = current[key]
            else:
                return False, f"Missing field: {field}"
    
    return True, "Valid callback data"