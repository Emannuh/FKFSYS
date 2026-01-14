from django import forms
from django.core.exceptions import ValidationError
from fkf_league.validators import normalize_kenya_phone
from fkf_league.constants import KENYA_COUNTIES
from .models import TeamOfficial

class TeamOfficialForm(forms.ModelForm):
    """Form for adding team officials"""
    
    phone_digits = forms.CharField(
        max_length=9,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '712345678',
            'pattern': '[0-9]{9}',
            'maxlength': '9'
        }),
        label='Phone Number',
        help_text='Enter 9 digits only (e.g., 712345678)'
    )
    
    class Meta:
        model = TeamOfficial
        fields = [
            'position', 'full_name', 'id_number',
            'caf_license_number', 'license_expiry_date', 'photo'
        ]
        widgets = {
            'position': forms.Select(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID Number'}),
            'caf_license_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'CAF License Number (for coaches only)'
            }),
            'license_expiry_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'position': 'Position/Role',
            'full_name': 'Full Name',
            'id_number': 'ID Number',
            'caf_license_number': 'CAF License Number',
            'license_expiry_date': 'License Expiry Date',
            'photo': 'Photo (Optional)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make CAF license fields optional initially
        self.fields['caf_license_number'].required = False
        self.fields['license_expiry_date'].required = False
        self.fields['photo'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        position = cleaned_data.get('position')
        caf_license = cleaned_data.get('caf_license_number')
        phone_digits = cleaned_data.get('phone_digits', '')
        
        # Coaches must have CAF license
        if position in ['head_coach', 'assistant_coach', 'goalkeeper_coach']:
            if not caf_license:
                raise forms.ValidationError(
                    f"{self.fields['position'].label} must have a CAF License Number."
                )
        
        # Validate and create phone number
        if phone_digits:
            # Remove any non-digit characters
            phone_digits = ''.join(filter(str.isdigit, phone_digits))
            
            if len(phone_digits) != 9:
                raise forms.ValidationError({'phone_digits': 'Please enter exactly 9 digits'})
            
            if not phone_digits[0] in ['0', '1', '7']:
                raise forms.ValidationError({'phone_digits': 'Phone number must start with 0, 1, or 7'})
            
            # Create full phone number with +254 prefix
            cleaned_data['phone_number'] = f'+254{phone_digits}'
        else:
            raise forms.ValidationError({'phone_digits': 'Phone number is required'})
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Set the phone_number from cleaned_data
        instance.phone_number = self.cleaned_data.get('phone_number', '')
        if commit:
            instance.save()
        return instance

        return cleaned_data
