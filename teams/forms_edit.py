from django import forms
from .models import Team

class TeamEditForm(forms.ModelForm):
    phone_digits = forms.CharField(
        max_length=9,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '712345678',
            'id': 'phone-input',
            'pattern': '[0-9]{9}',
            'maxlength': '9'
        }),
        help_text="Enter 9 digits only (e.g., 712345678). Will be saved as +254XXXXXXXXX"
    )

    class Meta:
        model = Team
        fields = [
            'team_name', 'location', 'home_ground', 
            'map_location', 'contact_person', 'email',
            'logo'
        ]
        widgets = {
            'team_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter team name'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Meru Town'}),
            'home_ground': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Meru Stadium'}),
            'map_location': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Google Maps URL (optional)'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Manager name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'manager@example.com'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prepopulate phone_digits from phone_number
        if self.instance and self.instance.phone_number:
            digits = self.instance.phone_number[-9:]
            self.fields['phone_digits'].initial = digits

    def clean(self):
        cleaned_data = super().clean()
        phone_digits = cleaned_data.get('phone_digits', '')
        if phone_digits:
            phone_digits = ''.join(filter(str.isdigit, phone_digits))
            if len(phone_digits) != 9:
                self.add_error('phone_digits', 'Please enter exactly 9 digits')
            if not phone_digits[0] in ['0', '1', '7']:
                self.add_error('phone_digits', 'Phone number must start with 0, 1, or 7')
            cleaned_data['phone_number'] = f'+254{phone_digits}'
        else:
            self.add_error('phone_digits', 'Phone number is required')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.phone_number = self.cleaned_data.get('phone_number', '')
        if commit:
            instance.save()
        return instance
