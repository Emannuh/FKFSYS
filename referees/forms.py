from django import forms
from .models import Referee, MatchReport
from matches.models import Match, Goal, Card
from teams.models import Player

class RefereeRegistrationForm(forms.ModelForm):
    class Meta:
        model = Referee
        fields = [
            'first_name', 'last_name', 'id_number',
            'phone_number', 'email', 'grade',
            'license_number', 'photo'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'grade': forms.Select(attrs={'class': 'form-control'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }

class MatchReportForm(forms.ModelForm):
    class Meta:
        model = MatchReport
        fields = [
            'weather_conditions', 'pitch_conditions',
            'attendance', 'major_incidents', 'referee_comments'
        ]
        widgets = {
            'weather_conditions': forms.TextInput(attrs={'class': 'form-control'}),
            'pitch_conditions': forms.Select(attrs={'class': 'form-control'}),
            'attendance': forms.NumberInput(attrs={'class': 'form-control'}),
            'major_incidents': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'referee_comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['scorer', 'minute', 'is_penalty', 'is_own_goal']
        widgets = {
            'scorer': forms.Select(attrs={'class': 'form-control'}),
            'minute': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_penalty': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_own_goal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, match=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if match:
            # Filter players to only those playing in this match
            home_players = Player.objects.filter(team=match.home_team)
            away_players = Player.objects.filter(team=match.away_team)
            players = home_players | away_players
            self.fields['scorer'].queryset = players

class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ['player', 'card_type', 'minute', 'reason']
        widgets = {
            'player': forms.Select(attrs={'class': 'form-control'}),
            'card_type': forms.Select(attrs={'class': 'form-control'}),
            'minute': forms.NumberInput(attrs={'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, match=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if match:
            home_players = Player.objects.filter(team=match.home_team)
            away_players = Player.objects.filter(team=match.away_team)
            players = home_players | away_players
            self.fields['player'].queryset = players

class MatchResultForm(forms.ModelForm):
    home_score = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )
    away_score = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )
    
    class Meta:
        model = Match
        fields = ['home_score', 'away_score', 'status']