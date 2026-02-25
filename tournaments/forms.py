from django import forms
from django.utils import timezone

from .models import (
    Tournament,
    TournamentTeamRegistration,
    TournamentPlayerRegistration,
    TournamentMatch,
    TournamentMatchOfficials,
    TournamentGroup,
    ExternalTeam,
    ExternalPlayer,
)
from teams.models import Team, Player
from referees.models import Referee


# ---------------------------------------------------------------------------
#  TOURNAMENT  (create / edit)
# ---------------------------------------------------------------------------
class TournamentForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d')
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d')
    )
    registration_deadline = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
    )

    class Meta:
        model = Tournament
        fields = [
            'name', 'description', 'banner', 'logo',
            'start_date', 'end_date', 'registration_deadline',
            'format', 'max_teams', 'min_squad_size', 'max_squad_size',
            'group_count', 'allow_external_teams', 'zone', 'venue',
            'rules', 'prize_info', 'entry_fee', 'status',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Meru Betika Football Challenge'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'format': forms.Select(attrs={'class': 'form-select'}),
            'max_teams': forms.NumberInput(attrs={'class': 'form-control'}),
            'min_squad_size': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_squad_size': forms.NumberInput(attrs={'class': 'form-control'}),
            'group_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'allow_external_teams': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'zone': forms.Select(attrs={'class': 'form-select'}),
            'venue': forms.TextInput(attrs={'class': 'form-control'}),
            'rules': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'prize_info': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'entry_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


# ---------------------------------------------------------------------------
#  TEAM REGISTRATION  (admin approves; team manager registers)
# ---------------------------------------------------------------------------
class TeamRegistrationForm(forms.Form):
    """Displayed to Team Managers to register their team for a tournament."""
    confirm = forms.BooleanField(
        label="I confirm that my team meets all entry requirements.",
        required=True,
    )


class TeamRegistrationReviewForm(forms.ModelForm):
    """Admin reviews and approves / rejects."""
    class Meta:
        model = TournamentTeamRegistration
        fields = ['status', 'rejection_reason', 'seed']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'rejection_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'seed': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# ---------------------------------------------------------------------------
#  PLAYER REGISTRATION  (team manager adds players to tournament squad)
# ---------------------------------------------------------------------------
class PlayerRegistrationForm(forms.Form):
    """Multi-select players from the team roster."""
    players = forms.ModelMultipleChoiceField(
        queryset=Player.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Select players for the tournament squad",
    )

    def __init__(self, *args, team=None, tournament=None, **kwargs):
        super().__init__(*args, **kwargs)
        if team:
            already = TournamentPlayerRegistration.objects.filter(
                tournament=tournament, player__team=team
            ).values_list('player_id', flat=True)
            self.fields['players'].queryset = Player.objects.filter(
                team=team
            ).exclude(id__in=already).order_by('jersey_number')


# ---------------------------------------------------------------------------
#  TOURNAMENT MATCH  (create / edit)
# ---------------------------------------------------------------------------
class TournamentMatchForm(forms.ModelForm):
    match_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )

    class Meta:
        model = TournamentMatch
        fields = [
            'stage', 'match_number', 'group',
            'home_team', 'away_team',
            'match_date', 'kickoff_time', 'venue',
            'referee', 'notes',
        ]
        widgets = {
            'stage': forms.Select(attrs={'class': 'form-select'}),
            'match_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'home_team': forms.Select(attrs={'class': 'form-select'}),
            'away_team': forms.Select(attrs={'class': 'form-select'}),
            'kickoff_time': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HH:MM'}),
            'venue': forms.TextInput(attrs={'class': 'form-control'}),
            'referee': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, tournament=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tournament:
            regs = TournamentTeamRegistration.objects.filter(
                tournament=tournament, status='approved'
            )
            self.fields['home_team'].queryset = regs
            self.fields['away_team'].queryset = regs
            self.fields['group'].queryset = TournamentGroup.objects.filter(
                tournament=tournament
            )


# ---------------------------------------------------------------------------
#  SCORE ENTRY (admin records result)
# ---------------------------------------------------------------------------
class MatchResultForm(forms.ModelForm):
    class Meta:
        model = TournamentMatch
        fields = ['home_score', 'away_score', 'home_penalties', 'away_penalties']
        widgets = {
            'home_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'away_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'home_penalties': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'away_penalties': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


# ---------------------------------------------------------------------------
#  EXTERNAL TEAM REGISTRATION  (for teams NOT in the league)
# ---------------------------------------------------------------------------
class ExternalTeamForm(forms.ModelForm):
    manager_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create a password for your portal'}),
        help_text='A portal account will be created so you can manage your team, register players, and view fixtures.',
        label='Portal Password',
    )

    class Meta:
        model = ExternalTeam
        fields = [
            'team_name', 'logo', 'location', 'home_ground',
            'contact_person', 'phone_number', 'email',
            'home_jersey_color', 'away_jersey_color',
        ]
        widgets = {
            'team_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Team name'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Nairobi, Kenya'}),
            'home_ground': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name of team manager'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254712345678'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'manager@example.com (used as login)'}),
            'home_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'away_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }

    def clean(self):
        cleaned = super().clean()
        # If no email provided, password field is irrelevant
        password = cleaned.get('manager_password')
        email = cleaned.get('email')
        if password and not email:
            self.add_error('email', 'Email is required to create a portal account.')
        return cleaned


# ---------------------------------------------------------------------------
#  EXTERNAL PLAYER REGISTRATION
# ---------------------------------------------------------------------------
class ExternalPlayerForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = ExternalPlayer
        fields = [
            'first_name', 'last_name', 'date_of_birth', 'id_number',
            'photo', 'position', 'jersey_number',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


# ---------------------------------------------------------------------------
#  IMPORT LEAGUE TEAMS  (admin bulk-imports existing league teams)
# ---------------------------------------------------------------------------
class ImportLeagueTeamsForm(forms.Form):
    """Admin selects which existing league teams to import into a tournament."""
    teams = forms.ModelMultipleChoiceField(
        queryset=Team.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Select FKF League teams to import",
    )

    def __init__(self, *args, tournament=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tournament:
            # Exclude teams already registered for this tournament
            already = TournamentTeamRegistration.objects.filter(
                tournament=tournament, team__isnull=False,
            ).values_list('team_id', flat=True)
            qs = Team.objects.filter(status='approved').exclude(id__in=already)
            if tournament.zone:
                qs = qs.filter(zone=tournament.zone)
            self.fields['teams'].queryset = qs.order_by('team_name')


# ---------------------------------------------------------------------------
#  TOURNAMENT MATCH OFFICIALS  (referee appointment)
# ---------------------------------------------------------------------------
class TournamentMatchOfficialsForm(forms.ModelForm):
    class Meta:
        model = TournamentMatchOfficials
        fields = [
            'main_referee', 'assistant_1', 'assistant_2',
            'fourth_official', 'match_commissioner', 'notes',
        ]
        widgets = {
            'main_referee': forms.Select(attrs={'class': 'form-select'}),
            'assistant_1': forms.Select(attrs={'class': 'form-select'}),
            'assistant_2': forms.Select(attrs={'class': 'form-select'}),
            'fourth_official': forms.Select(attrs={'class': 'form-select'}),
            'match_commissioner': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        approved = Referee.objects.filter(status='approved').order_by('first_name')
        for field_name in ['main_referee', 'assistant_1', 'assistant_2',
                           'fourth_official', 'match_commissioner']:
            self.fields[field_name].queryset = approved
            self.fields[field_name].required = False


# ---------------------------------------------------------------------------
#  FIXTURE GENERATION OPTIONS
# ---------------------------------------------------------------------------
class GenerateFixturesForm(forms.Form):
    """Admin chooses when fixtures start and interval between rounds."""
    first_match_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        label="First Match Date & Time",
    )
    days_between_rounds = forms.IntegerField(
        min_value=1, max_value=30, initial=7,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Days between rounds",
    )
    venue = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Default venue for all matches'}),
        label="Default Venue (leave blank to use tournament venue)",
    )
