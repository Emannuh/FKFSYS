import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .external_verification import FIFAConnectVerification, IPRSVerification
from .id_verification import DuplicatePlayerChecker, IDVerification
from .models import Player, Team, TeamOfficial

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
HEX_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')


def validate_image_size(upload):
    """Reject uploads over 5 MB (Pillow already verifies it is a real image)."""
    if upload and getattr(upload, 'size', 0) > MAX_UPLOAD_BYTES:
        raise ValidationError('Image too large - the maximum size is 5 MB.')


def _image_field(**kwargs):
    return forms.ImageField(
        required=False,
        validators=[validate_image_size],
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        **kwargs,
    )


class KenyaPhoneDigitsMixin:
    """Adds a ``phone_digits`` field (9 digits) that is saved as ``+254XXXXXXXXX``."""

    phone_field_name = 'phone_number'

    def _clean_phone_digits(self, cleaned_data):
        digits = ''.join(ch for ch in (cleaned_data.get('phone_digits') or '') if ch.isdigit())
        if not digits:
            self.add_error('phone_digits', 'Phone number is required')
        elif len(digits) != 9:
            self.add_error('phone_digits', 'Please enter exactly 9 digits')
        elif digits[0] not in '017':
            self.add_error('phone_digits', 'Phone number must start with 0, 1, or 7')
        else:
            cleaned_data[self.phone_field_name] = f'+254{digits}'
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        setattr(instance, self.phone_field_name, self.cleaned_data[self.phone_field_name])
        if commit:
            instance.save()
            self.save_m2m()
        return instance


def phone_digits_field(**attrs):
    return forms.CharField(
        max_length=9,
        label='Phone Number',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': '712345678',
            'pattern': '[0-9]{9}', 'maxlength': '9', 'inputmode': 'numeric', **attrs,
        }),
        help_text='Enter 9 digits only (e.g., 712345678). Will be saved as +254XXXXXXXXX',
    )


# ── Teams ───────────────────────────────────────────────────────────────────

class TeamInfoForm(KenyaPhoneDigitsMixin, forms.ModelForm):
    """Shared base for public registration and admin edits of team details."""

    phone_digits = phone_digits_field(id='phone-input')
    logo = _image_field()

    class Meta:
        model = Team
        fields = ['team_name', 'location', 'home_ground', 'map_location', 'contact_person', 'email', 'logo']
        widgets = {
            'team_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter team name'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Meru Town'}),
            'home_ground': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Meru Stadium'}),
            'map_location': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Google Maps URL (optional)'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Manager name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'manager@example.com'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.phone_number:
            self.fields['phone_digits'].initial = self.instance.phone_number[-9:]

    def clean(self):
        cleaned_data = super().clean()
        others = Team.objects.exclude(pk=self.instance.pk) if self.instance.pk else Team.objects.all()

        team_name = cleaned_data.get('team_name')
        if team_name and others.filter(team_name__iexact=team_name).exists():
            self.add_error('team_name', 'A team with this name already exists.')
        email = cleaned_data.get('email')
        if email and others.filter(email__iexact=email).exists():
            self.add_error('email', 'This email is already registered.')

        self._clean_phone_digits(cleaned_data)
        phone = cleaned_data.get('phone_number')
        if phone and others.filter(phone_number=phone).exists():
            self.add_error('phone_digits', 'This phone number is already registered to another team.')
        return cleaned_data


class TeamRegistrationForm(TeamInfoForm):
    """Public team registration (step 1 of 2, before payment)."""


class TeamEditForm(TeamInfoForm):
    """League admin/manager edit of team details."""


class TeamKitForm(forms.ModelForm):
    """Kit colours (validated #RRGGBB) and kit images for players and goalkeepers."""

    KITS = ('home', 'away', 'third', 'gk_home', 'gk_away', 'gk_third')
    PARTS = ('jersey', 'shorts', 'socks')
    OPTIONAL_KITS = ('third', 'gk_third')

    home_kit_image = _image_field()
    away_kit_image = _image_field()
    third_kit_image = _image_field()
    gk_home_kit_image = _image_field()
    gk_away_kit_image = _image_field()
    gk_third_kit_image = _image_field()

    class Meta:
        model = Team
        fields = [
            *(f'{kit}_{part}_color' for kit in ('home', 'away', 'third', 'gk_home', 'gk_away', 'gk_third')
              for part in ('jersey', 'shorts', 'socks')),
            'home_kit_image', 'away_kit_image', 'third_kit_image',
            'gk_home_kit_image', 'gk_away_kit_image', 'gk_third_kit_image',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for kit in self.KITS:
            for part in self.PARTS:
                field = self.fields[f'{kit}_{part}_color']
                field.required = kit not in self.OPTIONAL_KITS
                field.widget = forms.TextInput(attrs={'class': 'form-control', 'type': 'color'})

    def clean(self):
        cleaned = super().clean()
        for name, value in list(cleaned.items()):
            if name.endswith('_color') and value and not HEX_COLOR.match(value):
                self.add_error(name, 'Enter a colour in #RRGGBB format.')
        if self.errors:
            return cleaned

        def same(a, b):
            return (cleaned.get(f'{a}_jersey_color') == cleaned.get(f'{b}_jersey_color')
                    and cleaned.get(f'{a}_shorts_color') == cleaned.get(f'{b}_shorts_color'))

        if same('home', 'away'):
            raise ValidationError('Player Home and Away kits must be different!')
        if same('gk_home', 'home'):
            raise ValidationError('Goalkeeper Home kit must be different from Player Home kit!')
        if same('gk_away', 'away'):
            raise ValidationError('Goalkeeper Away kit must be different from Player Away kit!')
        return cleaned

    def save(self, commit=True):
        team = super().save(commit=False)
        team.kit_colors_set = True
        if commit:
            team.save()
        return team


# ── Players ─────────────────────────────────────────────────────────────────

class PlayerRegistrationForm(forms.ModelForm):
    """
    Register a player to ``team``: ID format, age (16-45), league-wide duplicate
    checks, jersey uniqueness, plus optional IPRS / FIFA Connect verification.
    """

    photo = _image_field()
    jersey_number = forms.IntegerField(min_value=1, max_value=99)

    class Meta:
        model = Player
        fields = [
            'first_name', 'last_name', 'date_of_birth', 'nationality', 'id_number',
            'fkf_license_number', 'license_expiry_date', 'position', 'jersey_number',
            'photo', 'is_captain',
        ]

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        self.fields['nationality'].required = False

    def clean_nationality(self):
        return self.cleaned_data.get('nationality') or 'Kenyan'

    def clean_id_number(self):
        id_number = IDVerification.validate_kenyan_id(self.cleaned_data.get('id_number'))
        DuplicatePlayerChecker.check_id_number(id_number, exclude_player_id=self.instance.pk)
        return id_number

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            IDVerification.check_age_eligibility(dob, min_age=16, max_age=45)
        return dob

    def clean_license_expiry_date(self):
        expiry = self.cleaned_data.get('license_expiry_date')
        if expiry and expiry < timezone.localdate():
            raise ValidationError('License expiry date cannot be in the past')
        return expiry

    def clean_jersey_number(self):
        number = self.cleaned_data.get('jersey_number')
        if number and self.team is not None:
            taken = Player.objects.filter(team=self.team, jersey_number=number).exclude(pk=self.instance.pk)
            if taken.exists():
                raise ValidationError(f'Jersey number {number} is already taken.')
        return number

    def clean(self):
        cleaned = super().clean()
        first, last = cleaned.get('first_name'), cleaned.get('last_name')
        dob, id_number = cleaned.get('date_of_birth'), cleaned.get('id_number')
        if not (first and last and dob and id_number) or self.errors:
            return cleaned

        DuplicatePlayerChecker.check_duplicate_by_name_dob(first, last, dob, exclude_player_id=self.instance.pk)

        iprs = IPRSVerification().verify_id_number(id_number, full_name=f'{first} {last}', date_of_birth=dob)
        if iprs['verified'] and not iprs['valid']:
            raise ValidationError(f"IPRS Verification Failed: {'; '.join(iprs['errors'])}")

        fifa = FIFAConnectVerification().verify_player({
            'first_name': first, 'last_name': last, 'date_of_birth': dob,
            'nationality': cleaned.get('nationality'),
        })
        if fifa['verified'] and not fifa['valid']:
            raise ValidationError(f"FIFA Connect Verification Failed: {'; '.join(fifa['errors'])}")

        self._record_verification(iprs, fifa)
        return cleaned

    def _record_verification(self, iprs, fifa):
        """Store verification outcome on the instance — no registry identity data is kept."""
        now = timezone.now()
        player = self.instance
        if iprs['verified']:
            player.iprs_verified = iprs['valid']
            player.iprs_verification_date = now
        if fifa['verified']:
            player.fifa_verified = fifa['valid']
            player.fifa_verification_date = now
            fifa_id = (fifa.get('data') or {}).get('fifa_id')
            if fifa_id:
                player.fifa_id = fifa_id
        player.verification_results = {
            'iprs': {k: iprs[k] for k in ('valid', 'verified', 'errors')},
            'fifa': {k: fifa[k] for k in ('valid', 'verified', 'errors')},
            'verified_at': now.isoformat(),
        }
        player.verification_warnings = '\n'.join([*iprs['errors'], *fifa['errors']])


class AdminPlayerForm(forms.ModelForm):
    """League staff edit of a player. Statistics are only editable by League Admins."""

    STAT_FIELDS = ('goals_scored', 'yellow_cards', 'red_cards', 'matches_played')

    photo = _image_field()
    jersey_number = forms.IntegerField(min_value=1, max_value=99)
    goals_scored = forms.IntegerField(min_value=0)
    yellow_cards = forms.IntegerField(min_value=0)
    red_cards = forms.IntegerField(min_value=0)
    matches_played = forms.IntegerField(min_value=0)

    class Meta:
        model = Player
        fields = [
            'first_name', 'last_name', 'date_of_birth', 'nationality', 'id_number', 'photo',
            'fkf_license_number', 'license_expiry_date', 'team', 'position', 'jersey_number',
            'is_captain', 'goals_scored', 'yellow_cards', 'red_cards', 'matches_played',
        ]

    def __init__(self, *args, can_edit_stats=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['team'].queryset = Team.objects.filter(status=Team.Status.APPROVED)
        if not can_edit_stats:
            for name in self.STAT_FIELDS:
                del self.fields[name]

    def clean_id_number(self):
        return IDVerification.validate_kenyan_id(self.cleaned_data.get('id_number'))

    def changed_stats(self):
        """[(field, old, new)] for statistics changed by this form."""
        return [
            (name, self.initial.get(name), self.cleaned_data[name])
            for name in self.STAT_FIELDS
            if name in self.fields and name in self.changed_data
        ]


# ── Team officials ──────────────────────────────────────────────────────────

class TeamOfficialForm(KenyaPhoneDigitsMixin, forms.ModelForm):
    """Add an official to ``team`` (coaches need a CAF licence; one per position)."""

    phone_digits = phone_digits_field()
    photo = _image_field(label='Photo (Optional)')

    class Meta:
        model = TeamOfficial
        fields = ['position', 'full_name', 'id_number', 'caf_license_number', 'license_expiry_date', 'photo']
        widgets = {
            'position': forms.Select(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID Number'}),
            'caf_license_number': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'CAF License Number (for coaches only)'}),
            'license_expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {'position': 'Position/Role'}

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team

    def get_team(self):
        return self.team

    def clean(self):
        cleaned = super().clean()
        position = cleaned.get('position')
        if position in TeamOfficial.COACH_POSITIONS and not cleaned.get('caf_license_number'):
            self.add_error('caf_license_number', 'Coaches must have a CAF License Number.')
        team = self.get_team()
        if team is not None and position and TeamOfficial.objects.filter(
            team=team, position=position
        ).exclude(pk=self.instance.pk).exists():
            self.add_error('position', 'This team already has an official in this position.')
        self._clean_phone_digits(cleaned)
        return cleaned

    def save(self, commit=True):
        if self.get_team() is not None:
            self.instance.team = self.get_team()
        return super().save(commit=commit)


class AdminTeamOfficialForm(TeamOfficialForm):
    """League staff version: the team is chosen in the form."""

    team = forms.ModelChoiceField(
        queryset=Team.objects.filter(status=Team.Status.APPROVED),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta(TeamOfficialForm.Meta):
        fields = ['team', *TeamOfficialForm.Meta.fields]

    def get_team(self):
        return self.cleaned_data.get('team') if hasattr(self, 'cleaned_data') else None
