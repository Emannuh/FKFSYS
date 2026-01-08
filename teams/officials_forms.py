from django import forms
from .models import TeamOfficial

class TeamOfficialForm(forms.ModelForm):
    """Form for adding team officials"""
    
    class Meta:
        model = TeamOfficial
        fields = [
            'position', 'full_name', 'id_number', 'phone_number',
            'caf_license_number', 'license_expiry_date', 'photo'
        ]
        widgets = {
            'position': forms.Select(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID Number'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07XXXXXXXX'}),
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
            'phone_number': 'Phone Number',
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
        
        # Coaches must have CAF license
        if position in ['head_coach', 'assistant_coach', 'goalkeeper_coach']:
            if not caf_license:
                raise forms.ValidationError(
                    f"{self.fields['position'].label} must have a CAF License Number."
                )
        
        return cleaned_data
