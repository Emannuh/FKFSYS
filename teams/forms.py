from django import forms
from .models import Team, Player
import googlemaps

class TeamRegistrationForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = [
            'team_name', 'location', 'home_ground', 
            'map_location', 'contact_person', 'phone_number', 'email',
            'logo'
        ]
        widgets = {
            'team_name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'home_ground': forms.TextInput(attrs={'class': 'form-control'}),
            'map_location': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Google Maps URL'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_map_location(self):
        map_url = self.cleaned_data.get('map_location')
        if map_url:
            # Basic validation for Google Maps URL
            if not ('maps.google.com' in map_url or 'goo.gl/maps' in map_url):
                raise forms.ValidationError("Please enter a valid Google Maps URL")
        return map_url

class PlayerRegistrationForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = [
            'first_name', 'last_name', 'date_of_birth', 
            'id_number', 'position', 'jersey_number', 'photo',
            'is_captain'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'is_captain': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }