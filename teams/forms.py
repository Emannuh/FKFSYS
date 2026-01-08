from django import forms
from .models import Team, Player
from django.core.exceptions import ValidationError
import datetime

class TeamRegistrationForm(forms.ModelForm):
    captain_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Captain Name (Optional)'
        })
    )
    
    coordinates = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., -0.05181, 37.6456'
        })
    )
    
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '712345678',
            'id': 'phone-input'
        }),
        help_text="Enter 9 digits starting with 7 (e.g., 712345678). It will be saved as +254712345678"
    )

    class Meta:
        model = Team
        fields = [
            'team_name', 'location', 'home_ground', 
            'map_location', 'contact_person', 'phone_number', 'email',
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
    
    def clean(self):
        cleaned_data = super().clean()
        team_name = cleaned_data.get('team_name')
        phone_number = cleaned_data.get('phone_number')
        email = cleaned_data.get('email')
        
        if team_name and Team.objects.filter(team_name__iexact=team_name).exists():
            raise ValidationError(f'Team "{team_name}" already exists!')
        
        # Phone validation is done in clean_phone_number
        
        if email and Team.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered!')
        
        return cleaned_data
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '')
        if not phone:
            raise forms.ValidationError("Phone number is required")
        
        # Remove all non-digits
        phone = ''.join(filter(str.isdigit, phone))
        
        # Handle different formats
        if len(phone) == 9 and phone.startswith('7'):
            # Format as +254712345678
            phone = '+254' + phone
        elif len(phone) == 10 and phone.startswith('07'):
            # Format 0712345678 -> +254712345678
            phone = '+254' + phone[1:]
        elif len(phone) == 12 and phone.startswith('254'):
            # Format 254712345678 -> +254712345678
            phone = '+' + phone
        elif len(phone) == 13 and phone.startswith('+254'):
            # Already in correct format
            pass
        else:
            raise forms.ValidationError(
                "Enter valid phone number (9 digits starting with 7, e.g., 712345678). "
                "It will be saved as +254712345678"
            )
        
        # Final validation - should be exactly +254 followed by 9 digits
        if not (len(phone) == 13 and phone.startswith('+254') and phone[4:].isdigit() and phone[4] == '7'):
            raise forms.ValidationError("Invalid phone number format. Must be +254 followed by 9 digits starting with 7")
        
        # Check if already exists
        if Team.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("This phone number is already registered!")
        
        return phone

class TeamManagerLoginForm(forms.Form):
    team_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your Team Code'
        }),
        label="Team Code"
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        team_code = cleaned_data.get('team_code')
        password = cleaned_data.get('password')
        
        if team_code and password:
            try:
                team = Team.objects.get(team_code=team_code)
                cleaned_data['team'] = team
            except Team.DoesNotExist:
                raise forms.ValidationError("Invalid team code")
        
        return cleaned_data


class PlayerRegistrationForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = [
            'first_name', 'last_name', 'date_of_birth', 
            'id_number', 'fkf_license_number', 'license_expiry_date',
            'position', 'jersey_number', 'photo', 'is_captain'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID/Passport Number'}),
            'fkf_license_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FKF License Number (Optional)'}),
            'license_expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 10', 'min': '1', 'max': '99'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'is_captain': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_jersey_number(self):
        jersey_number = self.cleaned_data.get('jersey_number')
        if jersey_number is not None:
            if jersey_number < 1 or jersey_number > 99:
                raise forms.ValidationError("Jersey number must be between 1 and 99")
        return jersey_number
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = datetime.date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 16:
                raise forms.ValidationError("Player must be at least 16 years old")
            if age > 45:
                raise forms.ValidationError("Player cannot be older than 45 years")
        return dob
    
    def clean_license_expiry_date(self):
        expiry_date = self.cleaned_data.get('license_expiry_date')
        if expiry_date:
            if expiry_date < datetime.date.today():
                raise forms.ValidationError("License expiry date cannot be in the past")
        return expiry_date


class TeamKitForm(forms.ModelForm):
    """Form for team to select kit colors including GK kits"""
    
    class Meta:
        model = Team
        fields = [
            # Player Kits
            'home_jersey_color', 'home_shorts_color', 'home_socks_color',
            'away_jersey_color', 'away_shorts_color', 'away_socks_color',
            'third_jersey_color', 'third_shorts_color', 'third_socks_color',
            # GK Kits
            'gk_home_jersey_color', 'gk_home_shorts_color', 'gk_home_socks_color',
            'gk_away_jersey_color', 'gk_away_shorts_color', 'gk_away_socks_color',
            'gk_third_jersey_color', 'gk_third_shorts_color', 'gk_third_socks_color',
        ]
        widgets = {
            # Player Home Kit
            'home_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'home_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'home_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # Player Away Kit
            'away_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'away_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'away_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # Player Third Kit
            'third_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'third_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'third_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # GK Home Kit
            'gk_home_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_home_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_home_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # GK Away Kit
            'gk_away_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_away_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_away_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            # GK Third Kit
            'gk_third_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_third_shorts_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'gk_third_socks_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Check player kits are different
        player_home_same = (
            cleaned_data.get('home_jersey_color') == cleaned_data.get('away_jersey_color') and
            cleaned_data.get('home_shorts_color') == cleaned_data.get('away_shorts_color')
        )
        
        # Check GK kits are different from player kits
        gk_home_diff_player_home = (
            cleaned_data.get('gk_home_jersey_color') != cleaned_data.get('home_jersey_color') or
            cleaned_data.get('gk_home_shorts_color') != cleaned_data.get('home_shorts_color')
        )
        
        gk_away_diff_player_away = (
            cleaned_data.get('gk_away_jersey_color') != cleaned_data.get('away_jersey_color') or
            cleaned_data.get('gk_away_shorts_color') != cleaned_data.get('away_shorts_color')
        )
        
        if player_home_same:
            raise forms.ValidationError("Player Home and Away kits must be different!")
        
        if not gk_home_diff_player_home:
            raise forms.ValidationError("Goalkeeper Home kit must be different from Player Home kit!")
        
        if not gk_away_diff_player_away:
            raise forms.ValidationError("Goalkeeper Away kit must be different from Player Away kit!")
        
        return cleaned_data