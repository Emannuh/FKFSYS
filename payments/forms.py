from django import forms
from .models import Payment

class PaymentForm(forms.ModelForm):
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '2547XXXXXXXX'
        })
    )
    
    class Meta:
        model = Payment
        fields = ['phone_number']