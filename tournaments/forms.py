from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from referees.models import Referee
from teams.models import Player, Team

from .models import (
    ExternalPlayer,
    ExternalTeam,
    Tournament,
    TournamentGroup,
    TournamentMatch,
    TournamentMatchOfficials,
    TournamentPlayerRegistration,
    TournamentTeamRegistration,
)

MAX_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

kickoff_validator = RegexValidator(
    r'^([01]\d|2[0-3]):[0-5]\d$', 'Enter a time as HH:MM (24-hour).'
)


def validate_image_upload(upload) -> None:
    """Size/type limits for user-supplied images (Pillow already checks content)."""
    if not upload or not hasattr(upload, 'content_type'):
        return  # unchanged existing file
    if upload.size > MAX_IMAGE_BYTES:
        raise ValidationError('Image must be 2 MB or smaller.')
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError('Upload a JPEG, PNG, WebP or GIF image.')


class ImageLimitMixin:
    image_fields: tuple[str, ...] = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.image_fields:
            if name in self.fields:
                self.fields[name].validators.append(validate_image_upload)


def _approved_registrations(tournament):
    return TournamentTeamRegistration.objects.filter(
        tournament=tournament, status=TournamentTeamRegistration.Status.APPROVED,
    ).select_related('team', 'external_team')


class TeamRegistrationLabelMixin:
    """Show registrations by team name instead of the default __str__."""
    def _label_team_fields(self, *names):
        for name in names:
            self.fields[name].label_from_instance = lambda r: r.display_name


# ---------------------------------------------------------------------------
#  TOURNAMENT  (create / edit)
# ---------------------------------------------------------------------------
class TournamentForm(ImageLimitMixin, forms.ModelForm):
    image_fields = ('banner', 'logo')

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

    def clean(self):
        cleaned = super().clean()
        lo, hi = cleaned.get('min_squad_size'), cleaned.get('max_squad_size')
        if lo is not None and hi is not None and lo > hi:
            self.add_error('max_squad_size', 'Maximum squad size cannot be below the minimum.')
        if cleaned.get('max_teams') is not None and cleaned['max_teams'] < 2:
            self.add_error('max_teams', 'A tournament needs at least 2 teams.')
        return cleaned


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

    def clean_status(self):
        status = self.cleaned_data['status']
        reg = self.instance
        if status == TournamentTeamRegistration.Status.APPROVED and reg.status != status:
            approved = reg.tournament.registrations.filter(
                status=TournamentTeamRegistration.Status.APPROVED,
            ).exclude(pk=reg.pk).count()
            if approved >= reg.tournament.max_teams:
                raise ValidationError(
                    f'The tournament already has {approved} approved teams (maximum {reg.tournament.max_teams}).'
                )
        return status


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
def _check_distinct_teams(form, cleaned):
    home, away = cleaned.get('home_team'), cleaned.get('away_team')
    if home and away and home == away:
        form.add_error('away_team', 'A team cannot play itself.')


class TournamentMatchForm(TeamRegistrationLabelMixin, forms.ModelForm):
    match_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )
    kickoff_time = forms.CharField(
        required=False, max_length=5, validators=[kickoff_validator],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HH:MM'}),
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
            'venue': forms.TextInput(attrs={'class': 'form-control'}),
            'referee': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, tournament, **kwargs):
        super().__init__(*args, **kwargs)
        self.tournament = tournament
        regs = _approved_registrations(tournament)
        self.fields['home_team'].queryset = regs
        self.fields['away_team'].queryset = regs
        self._label_team_fields('home_team', 'away_team')
        self.fields['group'].queryset = TournamentGroup.objects.filter(tournament=tournament)

    def clean(self):
        cleaned = super().clean()
        _check_distinct_teams(self, cleaned)
        stage, number = cleaned.get('stage'), cleaned.get('match_number')
        if stage and number and TournamentMatch.objects.filter(
            tournament=self.tournament, stage=stage, match_number=number,
        ).exclude(pk=self.instance.pk).exists():
            self.add_error('match_number', 'This match number is already used in that stage.')
        return cleaned


class TournamentMatchEditForm(TeamRegistrationLabelMixin, forms.ModelForm):
    """Admin edits schedule, duration and (for TBD knockout slots) the teams."""
    match_date = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
        label='Match Date & Time',
    )
    kickoff_time = forms.CharField(
        required=False, max_length=5, validators=[kickoff_validator],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 15:00'}),
        label='Kickoff Time (display)',
    )
    match_duration = forms.IntegerField(min_value=20, max_value=120, label='Total Duration (min)',
                                        widget=forms.NumberInput(attrs={'class': 'form-control'}))
    half_duration = forms.IntegerField(min_value=10, max_value=60, label='Half Duration (min)',
                                       widget=forms.NumberInput(attrs={'class': 'form-control'}))
    extra_time_duration = forms.IntegerField(min_value=0, max_value=60, label='Extra Time (min)',
                                             widget=forms.NumberInput(attrs={'class': 'form-control'}))

    class Meta:
        model = TournamentMatch
        fields = [
            'home_team', 'away_team', 'match_date', 'kickoff_time', 'venue',
            'match_duration', 'half_duration', 'extra_time_duration', 'notes',
        ]
        widgets = {
            'home_team': forms.Select(attrs={'class': 'form-select'}),
            'away_team': forms.Select(attrs={'class': 'form-select'}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Stadium name'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        regs = _approved_registrations(self.instance.tournament)
        self.fields['home_team'].queryset = regs
        self.fields['away_team'].queryset = regs
        self._label_team_fields('home_team', 'away_team')
        if self.instance.status == TournamentMatch.Status.COMPLETED:
            # Changing teams after a result would orphan the standings.
            for name in ('home_team', 'away_team'):
                self.fields[name].disabled = True

    def clean(self):
        cleaned = super().clean()
        _check_distinct_teams(self, cleaned)
        half, total = cleaned.get('half_duration'), cleaned.get('match_duration')
        if half and total and half * 2 > total:
            self.add_error('half_duration', 'Two halves cannot exceed the total duration.')
        return cleaned


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

    def clean(self):
        cleaned = super().clean()
        hs, as_ = cleaned.get('home_score'), cleaned.get('away_score')
        hp, ap = cleaned.get('home_penalties'), cleaned.get('away_penalties')
        if hs is None or as_ is None:
            return cleaned
        has_pens = hp is not None or ap is not None
        if not self.instance.is_knockout:
            if has_pens:
                raise ValidationError('Penalty shoot-outs only apply to knockout matches.')
        elif hs != as_:
            if has_pens:
                raise ValidationError('Penalties are only recorded when the score is level.')
        elif hp is None or ap is None or hp == ap:
            raise ValidationError('A drawn knockout match needs a penalty shoot-out winner.')
        return cleaned


# ---------------------------------------------------------------------------
#  EXTERNAL TEAM REGISTRATION  (for teams NOT in the league)
# ---------------------------------------------------------------------------
class ExternalTeamForm(ImageLimitMixin, forms.ModelForm):
    image_fields = ('logo',)

    manager_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='Create a password for your team portal account.',
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
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'manager@example.com'}),
            'home_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'away_jersey_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }

    def __init__(self, *args, tournament, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.tournament = tournament
        self.user = user
        if user.is_authenticated:
            # Logged-in managers link the team to their own account.
            del self.fields['manager_password']
        else:
            self.fields['email'].required = True
            self.fields['manager_password'].required = True

    def clean_team_name(self):
        name = self.cleaned_data['team_name'].strip()
        if ExternalTeam.objects.filter(tournament=self.tournament, team_name__iexact=name).exists():
            raise ValidationError('A team with this name is already registered for this tournament.')
        return name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not self.user.is_authenticated and email and \
                get_user_model().objects.filter(email__iexact=email).exists():
            # Never link to (or log in as) an existing account from a public form.
            raise ValidationError(
                'An account with this email already exists. Please log in first, then register your team.'
            )
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('manager_password')
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                self.add_error('manager_password', exc)
        return cleaned


# ---------------------------------------------------------------------------
#  EXTERNAL PLAYER REGISTRATION
# ---------------------------------------------------------------------------
class ExternalPlayerForm(ImageLimitMixin, forms.ModelForm):
    image_fields = ('photo',)

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

    def __init__(self, *args, external_team, **kwargs):
        super().__init__(*args, **kwargs)
        self.external_team = external_team

    def clean_jersey_number(self):
        number = self.cleaned_data['jersey_number']
        if self.external_team.players.filter(jersey_number=number).exists():
            raise ValidationError('This jersey number is already taken in your squad.')
        return number


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

    def __init__(self, *args, tournament, **kwargs):
        super().__init__(*args, **kwargs)
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
OFFICIAL_FIELDS = ('main_referee', 'assistant_1', 'assistant_2', 'fourth_official', 'match_commissioner')


class TournamentMatchOfficialsForm(forms.ModelForm):
    class Meta:
        model = TournamentMatchOfficials
        fields = [*OFFICIAL_FIELDS, 'notes']
        widgets = {
            **{name: forms.Select(attrs={'class': 'form-select'}) for name in OFFICIAL_FIELDS},
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        approved = Referee.objects.filter(status='approved').order_by('first_name')
        for name in OFFICIAL_FIELDS:
            self.fields[name].queryset = approved
            self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('main_referee'):
            self.add_error('main_referee', 'A main referee is required to appoint officials.')
        chosen = [cleaned.get(name) for name in OFFICIAL_FIELDS if cleaned.get(name)]
        if len(chosen) != len({r.pk for r in chosen}):
            raise ValidationError('The same referee cannot hold two roles in one match.')
        return cleaned


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
    replace_existing = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I understand this deletes all existing fixtures, results, squads and standings',
    )

    def __init__(self, *args, existing_matches: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.existing_matches = existing_matches
        if not existing_matches:
            del self.fields['replace_existing']

    def clean_replace_existing(self):
        value = self.cleaned_data.get('replace_existing')
        if self.existing_matches and not value:
            raise ValidationError(
                f'{self.existing_matches} fixtures already exist. Tick the box to replace them.'
            )
        return value
