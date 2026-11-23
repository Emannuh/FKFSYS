from django import forms
from django.core.validators import MinValueValidator

from .models import LeagueTable, Match


class MatchResultForm(forms.ModelForm):
    home_score = forms.IntegerField(min_value=0, max_value=99)
    away_score = forms.IntegerField(min_value=0, max_value=99)

    class Meta:
        model = Match
        fields = ['home_score', 'away_score']


class LeagueTableForm(forms.ModelForm):
    """Manual correction of a standings row. GD and points are always derived on save."""

    class Meta:
        model = LeagueTable
        fields = ['matches_played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.min_value = 0
            field.widget.attrs['min'] = 0
            field.validators.append(MinValueValidator(0))

    def clean(self):
        data = super().clean()
        parts = [data.get(k) for k in ('wins', 'draws', 'losses', 'matches_played')]
        if None not in parts and parts[0] + parts[1] + parts[2] != parts[3]:
            raise forms.ValidationError("Wins + draws + losses must equal matches played.")
        return data
