from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
from .models import Payment
from teams.models import Team
from .forms import PaymentForm
from .daraja import MpesaDarajaAPI

def payment_page(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            # Initialize Daraja API
            daraja = MpesaDarajaAPI()
            
            phone_number = form.cleaned_data['phone_number']
            amount = 1000  # Registration fee in KSh
            
            # Initiate payment
            response = daraja.lipa_na_mpesa_online(
                phone_number=phone_number,
                amount=amount,
                account_reference=team.team_code,
                transaction_desc=f"FKF Meru League Registration - {team.team_name}"
            )
            
            if response and response.get('ResponseCode') == '0':
                # Save payment record
                payment = Payment.objects.create(
                    team=team,
                    amount=amount,
                    phone_number=phone_number,
                    checkout_request_id=response.get('CheckoutRequestID'),
                    merchant_request_id=response.get('MerchantRequestID'),
                    status='pending'
                )
                
                messages.success(request, 'Payment initiated! Please check your phone to complete the payment.')
                return redirect('payment_status', payment_id=payment.id)
            else:
                messages.error(request, 'Failed to initiate payment. Please try again.')
    
    else:
        form = PaymentForm()
    
    return render(request, 'payments/payment.html', {
        'form': form,
        'team': team,
        'amount': 1000
    })

def payment_status(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Check payment status
    daraja = MpesaDarajaAPI()
    status_response = daraja.check_transaction_status(payment.checkout_request_id)
    
    if status_response:
        result_code = status_response.get('ResultCode')
        if result_code == '0':
            payment.status = 'completed'
            payment.mpesa_receipt_number = status_response.get('MpesaReceiptNumber')
            payment.result_code = result_code
            payment.result_desc = status_response.get('ResultDesc')
            payment.save()
            
            # Update team payment status
            team = payment.team
            team.payment_status = True
            team.payment_date = payment.transaction_date
            team.save()
            
            messages.success(request, 'Payment completed successfully!')
        else:
            payment.status = 'failed'
            payment.result_code = result_code
            payment.result_desc = status_response.get('ResultDesc')
            payment.save()
            
            messages.error(request, f'Payment failed: {status_response.get("ResultDesc")}')
    
    return render(request, 'payments/payment_status.html', {
        'payment': payment,
        'team': payment.team
    })

@csrf_exempt
def payment_callback(request):
    """Handle Daraja API callback"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract callback metadata
            callback_metadata = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {})
            
            # Find payment by checkout request ID
            checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
            
            if checkout_request_id:
                payment = Payment.objects.get(checkout_request_id=checkout_request_id)
                
                # Update payment with callback data
                if callback_metadata.get('Item'):
                    for item in callback_metadata['Item']:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            payment.mpesa_receipt_number = item.get('Value')
                        elif item.get('Name') == 'Amount':
                            payment.amount = item.get('Value')
                
                result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
                if result_code == 0:
                    payment.status = 'completed'
                    
                    # Update team
                    team = payment.team
                    team.payment_status = True
                    team.save()
                else:
                    payment.status = 'failed'
                
                payment.save()
            
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
        
        except Exception as e:
            print(f"Callback error: {e}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Failed'})
    
    return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid request method'})