from django import forms
from django.core.exceptions import ValidationError

from fkf_league.validators import normalize_kenya_phone


class PaymentForm(forms.Form):
    phone_number = forms.CharField(
        max_length=20,
        label="M-PESA phone number",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "+2547XXXXXXXX",
            "autocomplete": "tel",
            "inputmode": "tel",
        }),
    )

    def clean_phone_number(self):
        try:
            return normalize_kenya_phone(self.cleaned_data["phone_number"])
        except ValidationError as exc:
            raise ValidationError(exc.messages) from exc
