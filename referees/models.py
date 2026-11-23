"""Referees app models: referees, appointments, reports, matchday squads."""
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from fkf_league.constants import KENYA_COUNTIES
from fkf_league.validators import validate_kenya_phone

MAX_PHOTO_BYTES = 5 * 1024 * 1024


def validate_photo_size(file) -> None:
    """Reject uploads larger than MAX_PHOTO_BYTES."""
    if file and getattr(file, 'size', 0) > MAX_PHOTO_BYTES:
        raise ValidationError("Photo must be 5 MB or smaller.")


class Referee(models.Model):
    """
    Referee model - Simple registration with approval workflow
    """
    class Level(models.TextChoices):
        FIFA_ELITE = 'fifa_elite', 'FIFA Elite'
        FKF_PREMIER = 'fkf_premier', 'FKF Premier League'
        FKF_NATIONAL_SUPER = 'fkf_national_super', 'FKF National Super League'
        FKF_DIVISION_1 = 'fkf_division_1', 'FKF Division 1'
        FKF_DIVISION_2 = 'fkf_division_2', 'FKF Division 2'
        FKF_COUNTY = 'fkf_county', 'FKF County League'
        GRASSROOT = 'grassroot', 'Grassroot'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        SUSPENDED = 'suspended', 'Suspended'

    class Specialization(models.TextChoices):
        REFEREE = 'REFEREE', 'Referee'
        ASSISTANT_REFEREE = 'ASSISTANT_REFEREE', 'Assistant Referee'
        MATCH_COMMISSIONER = 'MATCH_COMMISSIONER', 'Match Commissioner'

    # User account (created after approval)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='referee_profile',
        null=True,
        blank=True,
        help_text="Linked user account (created after approval)"
    )

    # SIMPLE REGISTRATION - Only 4 fields required!
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    fkf_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="FKF License Number"
    )
    email = models.EmailField(unique=True)

    # Optional at registration
    phone_number = models.CharField(
        max_length=13,
        blank=True,
        validators=[validate_kenya_phone],
        verbose_name="Phone Number",
        help_text="Must be +254 followed by 9 digits (e.g., +254712345678)"
    )
    photo = models.ImageField(
        upload_to='referee_photos/', blank=True, null=True, validators=[validate_photo_size]
    )

    # Auto-generated after approval
    unique_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Unique Referee ID",
        help_text="Auto-generated login ID (REF-YYYY-XXXX)"
    )

    # Profile fields (filled later)
    level = models.CharField(
        max_length=30,
        choices=Level.choices,
        blank=True,
        null=True,
        verbose_name="Referee Level"
    )
    specialization = models.CharField(
        max_length=30,
        choices=Specialization.choices,
        blank=True,
        null=True,
        verbose_name="Specialization",
        help_text="Select your primary specialization: Referee, Assistant Referee, or Match Commissioner"
    )
    county = models.CharField(
        max_length=50,
        choices=KENYA_COUNTIES,
        blank=True,
        null=True,
        verbose_name="County"
    )
    id_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        verbose_name="National ID Number"
    )

    # Status Management
    is_active = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Approval Workflow
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_referees'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    suspension_reason = models.TextField(blank=True)

    # Timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Referee'
        verbose_name_plural = 'Referees'
        permissions = [
            ('manage_referees', 'Can manage referees (approve/reject/suspend)'),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.unique_id or 'Pending'}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def generate_unique_id(self) -> str:
        """Generate an unused login ID of the form REF-YYYY-XXXX."""
        year = timezone.now().year
        while True:
            unique_id = f"REF-{year}-{secrets.randbelow(10_000):04d}"
            if not Referee.objects.filter(unique_id=unique_id).exists():
                return unique_id

    def approve(self, approved_by_user: User) -> str:
        """
        Approve the referee and create their login account.

        The account is created with an *unusable* password: the referee sets
        their own password through the emailed set-password link (see
        ``referees.services.send_account_setup_email``). Returns the login ID.
        """
        if not self.unique_id:
            self.unique_id = self.generate_unique_id()

        if not self.user:
            user = User(
                username=self.unique_id,
                email=self.email,
                first_name=self.first_name,
                last_name=self.last_name,
            )
            user.set_unusable_password()
            user.save()
            self.user = user

        self.status = self.Status.APPROVED
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.rejection_reason = ''
        self.suspension_reason = ''
        self.is_active = True
        self.save()
        return self.unique_id

    def reject(self, reason: str = '') -> None:
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.is_active = False
        self.save()

    def suspend(self, reason: str = '') -> None:
        self.status = self.Status.SUSPENDED
        self.suspension_reason = reason
        self.is_active = False
        self.save()

    def reactivate(self) -> None:
        """Lift a suspension (or re-enable a deactivated approved referee)."""
        if self.status in (self.Status.SUSPENDED, self.Status.APPROVED):
            self.status = self.Status.APPROVED
            self.is_active = True
            self.suspension_reason = ''
            self.save()

    def can_be_appointed(self) -> bool:
        return self.status == self.Status.APPROVED and self.is_active


class RefereeAvailability(models.Model):
    """Track referee availability"""
    referee = models.ForeignKey(
        'Referee',
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    date = models.DateField()
    is_available = models.BooleanField(default=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['referee', 'date'], name='uniq_referee_availability_date'),
        ]
        verbose_name_plural = 'Referee Availabilities'
        ordering = ['-date']

    def __str__(self):
        status = "Available" if self.is_available else "Unavailable"
        return f"{self.referee.full_name} - {self.date} ({status})"


@dataclass(frozen=True)
class OfficialRole:
    """How one appointment role maps onto MatchOfficials columns."""
    code: str
    field: str          # FK to Referee
    label: str
    prefix: str | None  # prefix of the <prefix>_confirmed / _rejected columns, if tracked

    @property
    def tracked(self) -> bool:
        return self.prefix is not None


# Order matters: it is the precedence used to resolve a referee's role.
OFFICIAL_ROLE_SPECS: tuple[OfficialRole, ...] = (
    OfficialRole('REFEREE', 'main_referee', 'Referee', 'main'),
    OfficialRole('AR1', 'assistant_1', 'Assistant Referee 1', 'ar1'),
    OfficialRole('AR2', 'assistant_2', 'Assistant Referee 2', 'ar2'),
    OfficialRole('FOURTH', 'fourth_official', 'Reserve Referee', 'fourth'),
    OfficialRole('RESERVE', 'reserve_referee', 'Reserve Referee', 'reserve'),
    OfficialRole('VAR', 'var', 'Video Assistant Referee', 'var'),
    OfficialRole('AVAR1', 'avar1', 'Assistant VAR 1', None),
    OfficialRole('COMMISSIONER', 'match_commissioner', 'Match Commissioner', 'commissioner'),
    OfficialRole('RESERVE_AR', 'reserve_assistant', 'Reserve Assistant Referee', None),
    OfficialRole('AVAR2', 'avar2', 'Assistant VAR 2', None),
)
OFFICIAL_ROLES_BY_CODE = {r.code: r for r in OFFICIAL_ROLE_SPECS}


class MatchOfficials(models.Model):
    """
    Match officials with enhanced validation
    """
    class Role(models.TextChoices):
        REFEREE = 'REFEREE', 'Referee'
        AR1 = 'AR1', 'Assistant Referee 1'
        AR2 = 'AR2', 'Assistant Referee 2'
        RESERVE = 'RESERVE', 'Reserve Referee'
        RESERVE_AR = 'RESERVE_AR', 'Reserve Assistant Referee'
        VAR = 'VAR', 'Video Assistant Referee'
        AVAR1 = 'AVAR1', 'Assistant VAR 1'
        AVAR2 = 'AVAR2', 'Assistant VAR 2'
        COMMISSIONER = 'COMMISSIONER', 'Match Commissioner'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Appointment'
        APPOINTED = 'APPOINTED', 'Appointed - Awaiting Confirmation'
        CONFIRMED = 'CONFIRMED', 'Confirmed by All'
        REJECTED = 'REJECTED', 'Some Officials Rejected'
        ALTERNATE = 'ALTERNATE', 'Using Alternate Officials'
        COMPLETED = 'COMPLETED', 'Match Completed'
        CANCELLED = 'CANCELLED', 'Match Cancelled'

    match = models.OneToOneField(
        'matches.Match',
        on_delete=models.CASCADE,
        related_name='officials'
    )

    # Required officials
    main_referee = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_main'
    )
    assistant_1 = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_assistant1'
    )
    assistant_2 = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_assistant2'
    )

    # Optional officials
    reserve_referee = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_reserve'
    )
    reserve_assistant = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_reserve_assistant'
    )
    var = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_var'
    )
    avar1 = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_avar1'
    )
    avar2 = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_avar2'
    )
    fourth_official = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_fourth'
    )
    match_commissioner = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_as_commissioner'
    )

    # Emergency fallback (manual entry)
    main_referee_name = models.CharField(max_length=100, blank=True)
    main_referee_mobile = models.CharField(max_length=20, blank=True)
    ar1_name = models.CharField(max_length=100, blank=True)
    ar1_mobile = models.CharField(max_length=20, blank=True)
    ar2_name = models.CharField(max_length=100, blank=True)
    ar2_mobile = models.CharField(max_length=20, blank=True)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Confirmation tracking
    main_confirmed = models.BooleanField(default=False)
    main_confirmed_at = models.DateTimeField(null=True, blank=True)
    main_rejected = models.BooleanField(default=False)
    main_rejection_reason = models.TextField(blank=True)
    main_rejected_at = models.DateTimeField(null=True, blank=True)

    ar1_confirmed = models.BooleanField(default=False)
    ar1_confirmed_at = models.DateTimeField(null=True, blank=True)
    ar1_rejected = models.BooleanField(default=False)
    ar1_rejection_reason = models.TextField(blank=True)
    ar1_rejected_at = models.DateTimeField(null=True, blank=True)

    ar2_confirmed = models.BooleanField(default=False)
    ar2_confirmed_at = models.DateTimeField(null=True, blank=True)
    ar2_rejected = models.BooleanField(default=False)
    ar2_rejection_reason = models.TextField(blank=True)
    ar2_rejected_at = models.DateTimeField(null=True, blank=True)

    reserve_confirmed = models.BooleanField(default=False)
    reserve_rejected = models.BooleanField(default=False)
    reserve_rejection_reason = models.TextField(blank=True)

    var_confirmed = models.BooleanField(default=False)
    var_rejected = models.BooleanField(default=False)
    var_rejection_reason = models.TextField(blank=True)

    fourth_confirmed = models.BooleanField(default=False)
    fourth_rejected = models.BooleanField(default=False)
    fourth_rejection_reason = models.TextField(blank=True)

    commissioner_confirmed = models.BooleanField(default=False)
    commissioner_confirmed_at = models.DateTimeField(null=True, blank=True)
    commissioner_rejected = models.BooleanField(default=False)
    commissioner_rejection_reason = models.TextField(blank=True)

    # Workflow tracking
    appointment_made_at = models.DateTimeField(null=True, blank=True)
    appointment_made_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referee_appointments_made'
    )
    last_reminder_sent = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Match Officials'
        ordering = ['match__match_date']
        permissions = [
            ('appoint_referees', 'Can appoint match officials'),
            ('replace_referee', 'Can replace appointed referee'),
            ('confirm_appointment', 'Can confirm referee appointment'),
        ]

    def __str__(self):
        return f"Officials for {self.match}"

    def clean(self):
        """Appointment business rules (window, round order, eligibility, duplicates, availability)."""
        # Rule 1: 4-day appointment window (from both)
        if self.match and self.match.match_date:
            days_until_match = (self.match.match_date.date() - timezone.now().date()).days
            if days_until_match > 4 and self.status == self.Status.APPOINTED:
                raise ValidationError(
                    f"Cannot appoint referees yet. Match is in {days_until_match} days. "
                    f"Appointments can only be made within 4 days of match."
                )

        # Rule 2: Round sequencing - previous round in the zone must be fully appointed first
        if self.match and self.match.round_number > 1:
            from matches.models import Match
            previous_round = self.match.round_number - 1
            unappointed = list(
                Match.objects.filter(
                    zone=self.match.zone, round_number=previous_round, officials__isnull=True,
                )
                .exclude(status__in=['cancelled', 'postponed'])
                .select_related('home_team', 'away_team')[:4]
            )
            if unappointed:
                match_info = [f"{m.home_team} vs {m.away_team}" for m in unappointed[:3]]
                raise ValidationError(
                    f"Cannot appoint for Round {self.match.round_number} yet. "
                    f"Complete all appointments for Round {previous_round} first. "
                    f"Unappointed matches: {', '.join(match_info)}"
                    f"{' and more...' if len(unappointed) > 3 else ''}"
                )

        # Rule 3: Check referee approval status (from Document 1)
        officials = [
            (self.main_referee, 'Referee'),
            (self.assistant_1, 'Assistant Referee 1'),
            (self.assistant_2, 'Assistant Referee 2'),
            (self.reserve_referee, 'Reserve Referee'),
            (self.reserve_assistant, 'Reserve Assistant Referee'),
            (self.var, 'VAR'),
            (self.avar1, 'AVAR 1'),
            (self.avar2, 'AVAR 2'),
            (self.fourth_official, 'Reserve Referee'),
            (self.match_commissioner, 'Match Commissioner'),
        ]

        for referee, role in officials:
            if referee and not referee.can_be_appointed():
                raise ValidationError(
                    f"{referee.full_name} cannot be appointed as {role}. "
                    f"Status: {referee.get_status_display()}, Active: {referee.is_active}"
                )

        # Rule 4: No duplicate appointments (from both)
        referee_roles = {}
        for referee, role in officials:
            if referee:
                if referee in referee_roles:
                    raise ValidationError(
                        f"{referee.full_name} cannot be both "
                        f"{referee_roles[referee]} and {role}"
                    )
                referee_roles[referee] = role

        # Rule 5: Check availability (from Document 1)
        if self.match and self.match.match_date:
            for referee, role in officials:
                if referee:
                    unavailable = RefereeAvailability.objects.filter(
                        referee=referee,
                        date=self.match.match_date.date(),
                        is_available=False
                    ).first()

                    if unavailable:
                        raise ValidationError(
                            f"{referee.full_name} is unavailable on {self.match.match_date.date()}. "
                            f"Reason: {unavailable.reason}"
                        )

    def save(self, *args, **kwargs):
        """Save with optional validation bypass"""
        validate = kwargs.pop('validate', True)  # Default is True (validate)

        if self.status == self.Status.APPOINTED and not self.appointment_made_at:
            self.appointment_made_at = timezone.now()

        if self.main_confirmed and self.ar1_confirmed and self.ar2_confirmed:
            if self.status == self.Status.APPOINTED:
                self.status = self.Status.CONFIRMED

        if validate:
            self.full_clean()

        super().save(*args, **kwargs)

    @property
    def all_required_confirmed(self) -> bool:
        """Check if all required officials have confirmed"""
        return (
            (not self.main_referee_id or self.main_confirmed) and
            (not self.assistant_1_id or self.ar1_confirmed) and
            (not self.assistant_2_id or self.ar2_confirmed)
        )

    @property
    def appointment_deadline(self):
        if self.match and self.match.match_date:
            return self.match.match_date.date() - timedelta(days=4)
        return None

    @property
    def confirmation_deadline(self):
        if self.match and self.match.match_date:
            return self.match.match_date.date() - timedelta(days=2)
        return None

    @property
    def has_declined(self) -> bool:
        return any(self.is_declined(r) for r in OFFICIAL_ROLE_SPECS)

    # ---- role helpers -------------------------------------------------
    def role_of(self, referee) -> 'OfficialRole | None':
        """The role ``referee`` holds in this appointment (first match wins)."""
        if referee is None:
            return None
        for role in OFFICIAL_ROLE_SPECS:
            if getattr(self, f'{role.field}_id') == referee.pk:
                return role
        return None

    def appointed(self) -> list:
        """(role, referee) for every filled position."""
        return [
            (role, getattr(self, role.field))
            for role in OFFICIAL_ROLE_SPECS
            if getattr(self, f'{role.field}_id')
        ]

    def is_confirmed(self, role: OfficialRole) -> bool:
        return bool(role.tracked and getattr(self, f'{role.prefix}_confirmed'))

    def is_declined(self, role: OfficialRole) -> bool:
        return bool(role.tracked and getattr(self, f'{role.prefix}_rejected'))

    def _set_if_field(self, name: str, value) -> None:
        if any(f.name == name for f in self._meta.concrete_fields):
            setattr(self, name, value)

    def mark_confirmed(self, role: OfficialRole) -> None:
        if not role.tracked:
            return
        setattr(self, f'{role.prefix}_confirmed', True)
        self._set_if_field(f'{role.prefix}_confirmed_at', timezone.now())
        if self.all_required_confirmed and self.status == self.Status.APPOINTED:
            self.status = self.Status.CONFIRMED

    def mark_declined(self, role: OfficialRole, reason: str) -> None:
        if not role.tracked:
            return
        setattr(self, f'{role.prefix}_rejected', True)
        setattr(self, f'{role.prefix}_rejection_reason', reason)
        self._set_if_field(f'{role.prefix}_rejected_at', timezone.now())
        self.status = self.Status.REJECTED

    def reset_role(self, role: OfficialRole) -> None:
        """Clear confirmation/decline state, e.g. after a replacement."""
        if not role.tracked:
            return
        setattr(self, f'{role.prefix}_confirmed', False)
        setattr(self, f'{role.prefix}_rejected', False)
        setattr(self, f'{role.prefix}_rejection_reason', '')
        self._set_if_field(f'{role.prefix}_confirmed_at', None)
        self._set_if_field(f'{role.prefix}_rejected_at', None)

    def declined_roles(self) -> list[dict]:
        return [
            {
                'role': role.label,
                'referee': getattr(self, role.field),
                'reason': getattr(self, f'{role.prefix}_rejection_reason'),
                'declined_at': getattr(self, f'{role.prefix}_rejected_at', None),
            }
            for role in OFFICIAL_ROLE_SPECS
            if self.is_declined(role)
        ]

    def get_appointed_officials_list(self) -> list[dict]:
        """Template helper: every appointed official with confirmation state."""
        return [
            {
                'role_code': role.code,
                'role_name': role.label,
                'referee': referee,
                'confirmed': self.is_confirmed(role),
            }
            for role, referee in self.appointed()
        ]


class TeamOfficial(models.Model):
    """Team officials for a match"""
    POSITION_CHOICES = [
        ('coach', 'Coach'),
        ('team_manager', 'Team Manager'),
        ('assistant_coach', 'Assistant Coach'),
        ('doctor', 'Team Doctor'),
        ('physio', 'Physiotherapist'),
        ('kit_manager', 'Kit Manager'),
        ('other', 'Other'),
    ]

    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='team_officials')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    position = models.CharField(max_length=20, choices=POSITION_CHOICES)
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['team', 'position']

    def __str__(self):
        return f"{self.name} - {self.get_position_display()} ({self.team})"


class PlayingKit(models.Model):
    """Track playing kit conditions"""
    KIT_ITEMS = [
        ('jersey', 'Jersey'),
        ('shorts', 'Shorts'),
        ('stockings', 'Stockings'),
        ('goalkeeper_jersey', 'Goalkeeper Jersey'),
        ('goalkeeper_shorts', 'Goalkeeper Shorts/Trousers'),
        ('goalkeeper_stockings', 'Goalkeeper Stockings'),
    ]

    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='playing_kits')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    item = models.CharField(max_length=50, choices=KIT_ITEMS)
    condition = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['match', 'team', 'item'], name='uniq_playingkit_match_team_item'),
        ]

    def __str__(self):
        return f"{self.get_item_display()} - {self.team}"


class MatchVenueDetails(models.Model):
    """Venue conditions and facilities"""
    PITCH_CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('very_poor', 'Very Poor'),
    ]

    match = models.OneToOneField('matches.Match', on_delete=models.CASCADE, related_name='venue_details')

    # Facilities
    home_changing_room = models.BooleanField(default=True)
    away_changing_room = models.BooleanField(default=True)
    seating_arrangement = models.BooleanField(default=True)
    ball_boys = models.BooleanField(default=True)
    security_personnel = models.BooleanField(default=True)
    field_markings = models.BooleanField(default=True)
    ambulance = models.BooleanField(default=True)
    stretcher = models.BooleanField(default=True)

    pitch_condition = models.CharField(max_length=20, choices=PITCH_CONDITION_CHOICES, default='good')
    weather_before = models.CharField(max_length=100, blank=True)
    weather_during = models.CharField(max_length=100, blank=True)

    # Match timing
    first_half_start = models.TimeField(null=True, blank=True)
    first_half_end = models.TimeField(null=True, blank=True)
    first_half_duration = models.IntegerField(null=True, blank=True)
    second_half_start = models.TimeField(null=True, blank=True)
    second_half_end = models.TimeField(null=True, blank=True)
    second_half_duration = models.IntegerField(null=True, blank=True)
    attendance = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Venue Details - {self.match}"


class StartingLineup(models.Model):
    """Starting 11 players"""
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='starting_lineups')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    player = models.ForeignKey('teams.Player', on_delete=models.CASCADE)
    jersey_number = models.IntegerField()
    position = models.CharField(max_length=50, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['match', 'team', 'player'], name='uniq_startinglineup_player'),
        ]
        ordering = ['jersey_number']

    def __str__(self):
        return f"{self.player} (#{self.jersey_number})"


class ReservePlayer(models.Model):
    """Substitute bench"""
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='reserve_players')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    player = models.ForeignKey('teams.Player', on_delete=models.CASCADE)
    jersey_number = models.IntegerField()
    not_working = models.BooleanField(default=False, help_text="Tick if this reserve player was not available/working.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['match', 'team', 'player'], name='uniq_reserveplayer_player'),
        ]
        ordering = ['jersey_number']

    def __str__(self):
        return f"{self.player} (#{self.jersey_number}) - Reserve"


class Substitution(models.Model):
    """Player substitutions"""
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='substitutions')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    minute = models.IntegerField()
    player_out = models.ForeignKey('teams.Player', on_delete=models.CASCADE, related_name='substituted_out')
    player_in = models.ForeignKey('teams.Player', on_delete=models.CASCADE, related_name='substituted_in')
    jersey_out = models.IntegerField()
    jersey_in = models.IntegerField()

    class Meta:
        ordering = ['minute']

    def __str__(self):
        return f"{self.minute}' - {self.player_out} → {self.player_in}"


class Caution(models.Model):
    """Yellow cards"""
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='cautions')
    player = models.ForeignKey('teams.Player', on_delete=models.CASCADE)
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    minute = models.IntegerField()
    reason = models.TextField()
    jersey_number = models.IntegerField()

    class Meta:
        ordering = ['minute']

    def __str__(self):
        return f"Yellow - {self.player} ({self.minute}')"


class Expulsion(models.Model):
    """Red cards"""
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='expulsions')
    player = models.ForeignKey('teams.Player', on_delete=models.CASCADE)
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    minute = models.IntegerField()
    reason = models.TextField()
    jersey_number = models.IntegerField()

    class Meta:
        ordering = ['minute']

    def __str__(self):
        return f"Red - {self.player} ({self.minute}')"


class MatchGoal(models.Model):
    """Goals scored"""
    class GoalType(models.TextChoices):
        NORMAL = 'normal', 'Normal Goal'
        PENALTY = 'penalty', 'Penalty'
        OWN_GOAL = 'own_goal', 'Own Goal'
        FREE_KICK = 'free_kick', 'Free Kick'

    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='match_goals')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    player = models.ForeignKey('teams.Player', on_delete=models.CASCADE, related_name='referee_match_goals')
    assist_by = models.ForeignKey(
        'teams.Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referee_goal_assists'
    )
    minute = models.IntegerField()
    goal_type = models.CharField(max_length=20, choices=GoalType.choices, default=GoalType.NORMAL)
    jersey_number = models.IntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['minute']

    def __str__(self):
        return f"{self.minute}' - {self.player} ({self.team})"


class PreMatchMeetingForm(models.Model):
    """Pre-match meeting form - filled by main referee 36 hours before match"""
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Submission'
        SUBMITTED = 'submitted', 'Submitted - Awaiting League Admin Approval'
        ADMIN_APPROVED = 'admin_approved', 'Admin Approved - Awaiting Referee Manager Approval'
        APPROVED = 'approved', 'Fully Approved'
        REJECTED = 'rejected', 'Rejected'

    match = models.OneToOneField('matches.Match', on_delete=models.CASCADE, related_name='pre_match_form')
    referee = models.ForeignKey(Referee, on_delete=models.CASCADE, related_name='pre_match_forms')
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)

    # Match Details (auto-filled)
    match_date = models.DateField()
    match_number = models.CharField(max_length=50, blank=True)
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    venue = models.CharField(max_length=200)
    city = models.CharField(max_length=100, blank=True)
    stadium = models.CharField(max_length=200, blank=True)

    # Schedule
    scheduled_time = models.TimeField(null=True, blank=True)
    actual_time = models.TimeField(null=True, blank=True)
    meeting_end_time = models.TimeField(null=True, blank=True)

    # Match Officials (auto-filled from MatchOfficials)
    match_commissioner_name = models.CharField(max_length=100, blank=True)
    match_commissioner_license = models.CharField(max_length=50, blank=True)
    match_commissioner_mobile = models.CharField(max_length=20, blank=True)

    centre_referee_name = models.CharField(max_length=100, blank=True)
    centre_referee_license = models.CharField(max_length=50, blank=True)
    centre_referee_mobile = models.CharField(max_length=20, blank=True)

    asst1_referee_name = models.CharField(max_length=100, blank=True)
    asst1_referee_license = models.CharField(max_length=50, blank=True)
    asst1_referee_mobile = models.CharField(max_length=20, blank=True)

    asst2_referee_name = models.CharField(max_length=100, blank=True)
    asst2_referee_license = models.CharField(max_length=50, blank=True)
    asst2_referee_mobile = models.CharField(max_length=20, blank=True)

    fourth_official_name = models.CharField(max_length=100, blank=True)
    fourth_official_license = models.CharField(max_length=50, blank=True)
    fourth_official_mobile = models.CharField(max_length=20, blank=True)

    # Home Team Officials
    home_head_coach = models.CharField(max_length=100, blank=True)
    home_head_coach_license = models.CharField(max_length=50, blank=True)
    home_head_coach_mobile = models.CharField(max_length=20, blank=True)

    home_team_manager = models.CharField(max_length=100, blank=True)
    home_team_manager_license = models.CharField(max_length=50, blank=True)
    home_team_manager_mobile = models.CharField(max_length=20, blank=True)

    home_team_doctor = models.CharField(max_length=100, blank=True)
    home_team_doctor_license = models.CharField(max_length=50, blank=True)
    home_team_doctor_mobile = models.CharField(max_length=20, blank=True)

    # Away Team Officials
    away_head_coach = models.CharField(max_length=100, blank=True)
    away_head_coach_license = models.CharField(max_length=50, blank=True)
    away_head_coach_mobile = models.CharField(max_length=20, blank=True)

    away_team_manager = models.CharField(max_length=100, blank=True)
    away_team_manager_license = models.CharField(max_length=50, blank=True)
    away_team_manager_mobile = models.CharField(max_length=20, blank=True)

    away_team_doctor = models.CharField(max_length=100, blank=True)
    away_team_doctor_license = models.CharField(max_length=50, blank=True)
    away_team_doctor_mobile = models.CharField(max_length=20, blank=True)

    # Home Team Uniforms (auto-filled from team kit)
    home_gk_shirt_color = models.CharField(max_length=50, blank=True)
    home_gk_shirt_number = models.CharField(max_length=10, blank=True)
    home_gk_short_track = models.CharField(max_length=50, blank=True)

    # Playing unit colours
    home_playing_unit_shirt = models.CharField(max_length=50, blank=True)
    home_playing_unit_short = models.CharField(max_length=50, blank=True)
    home_playing_unit_stocking = models.CharField(max_length=50, blank=True)

    home_reserve_gk_shirt = models.CharField(max_length=50, blank=True)
    home_reserve_gk_short_track = models.CharField(max_length=50, blank=True)
    home_reserve_gk_stocking = models.CharField(max_length=50, blank=True)

    home_official_shirt = models.CharField(max_length=50, blank=True)
    home_official_short = models.CharField(max_length=50, blank=True)
    home_official_stocking = models.CharField(max_length=50, blank=True)

    home_warm_up_kit = models.CharField(max_length=50, blank=True)
    home_reserve_track_suit = models.CharField(max_length=50, blank=True)

    # Away Team Uniforms (auto-filled from team kit)
    away_gk_shirt_color = models.CharField(max_length=50, blank=True)
    away_gk_shirt_number = models.CharField(max_length=10, blank=True)
    away_gk_short_track = models.CharField(max_length=50, blank=True)

    # Playing unit colours
    away_playing_unit_shirt = models.CharField(max_length=50, blank=True)
    away_playing_unit_short = models.CharField(max_length=50, blank=True)
    away_playing_unit_stocking = models.CharField(max_length=50, blank=True)

    away_reserve_gk_shirt = models.CharField(max_length=50, blank=True)
    away_reserve_gk_short_track = models.CharField(max_length=50, blank=True)
    away_reserve_gk_stocking = models.CharField(max_length=50, blank=True)

    away_official_shirt = models.CharField(max_length=50, blank=True)
    away_official_short = models.CharField(max_length=50, blank=True)
    away_official_stocking = models.CharField(max_length=50, blank=True)

    away_warm_up_kit = models.CharField(max_length=50, blank=True)
    away_reserve_track_suit = models.CharField(max_length=50, blank=True)

    # Field Captain
    home_field_captain_name = models.CharField(max_length=100, blank=True)
    home_field_captain_number = models.CharField(max_length=10, blank=True)
    home_field_captain_arm_band = models.CharField(max_length=50, blank=True)

    away_field_captain_name = models.CharField(max_length=100, blank=True)
    away_field_captain_number = models.CharField(max_length=10, blank=True)
    away_field_captain_arm_band = models.CharField(max_length=50, blank=True)

    # Management of the Match
    reporting_time = models.TimeField(null=True, blank=True)
    checking_time = models.TimeField(null=True, blank=True)
    kick_off_time = models.TimeField(null=True, blank=True)

    number_ball_boys = models.IntegerField(null=True, blank=True)
    shirt_color = models.CharField(max_length=50, blank=True)
    or_bib_color = models.CharField(max_length=50, blank=True)

    home_balls_available = models.IntegerField(null=True, blank=True)
    away_balls_available = models.IntegerField(null=True, blank=True)
    expected_spectators = models.IntegerField(null=True, blank=True)

    # Medical Ground
    quality_personnel = models.CharField(max_length=100, blank=True)
    doctor_available = models.BooleanField(default=False)
    physiotherapist_available = models.BooleanField(default=False)
    clinical_officer_first_aid = models.BooleanField(default=False)

    stretcher_available = models.BooleanField(default=False)
    stretcher_not_available = models.BooleanField(default=False)
    stretcher_how_many = models.IntegerField(null=True, blank=True)

    first_aid_bag = models.BooleanField(default=False)
    ambulance_available = models.BooleanField(default=False)
    booked_hospital = models.CharField(max_length=200, blank=True)

    sitting_arrangement = models.CharField(max_length=100, blank=True)

    dressing_room_home = models.BooleanField(default=False)
    dressing_room_away = models.BooleanField(default=False)
    dressing_room_officials = models.BooleanField(default=False)
    dressing_room_not_available = models.BooleanField(default=False)

    # Security
    security_entrance = models.BooleanField(default=False)
    security_main_gate = models.BooleanField(default=False)
    security_other_gate = models.BooleanField(default=False)

    police_in_uniform = models.BooleanField(default=False)
    police_plain_clothes = models.BooleanField(default=False)
    or_guards = models.BooleanField(default=False)
    and_company_name = models.CharField(max_length=200, blank=True)
    nearest_police_post = models.CharField(max_length=200, blank=True)

    # In Attendance (free text for additional personnel)
    attendance_notes = models.TextField(blank=True)

    # Officials sections
    home_officials_notes = models.TextField(blank=True)
    away_officials_notes = models.TextField(blank=True)

    # Workflow
    submitted_at = models.DateTimeField(null=True, blank=True)

    admin_approved_at = models.DateTimeField(null=True, blank=True)
    admin_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_approved_prematch_forms'
    )
    admin_rejection_reason = models.TextField(blank=True)

    manager_approved_at = models.DateTimeField(null=True, blank=True)
    manager_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manager_approved_prematch_forms'
    )
    manager_rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Track if form is locked after match
    is_locked = models.BooleanField(default=False)

    class Meta:
        ordering = ['-match__match_date']
        permissions = [
            ('submit_prematch_form', 'Can submit pre-match meeting form'),
            ('approve_prematch_form_admin', 'Can approve pre-match form as admin'),
            ('approve_prematch_form_manager', 'Can approve pre-match form as manager'),
        ]

    def __str__(self):
        return f"Pre-Match Form - {self.match} ({self.get_status_display()})"


class MatchReport(models.Model):
    """Comprehensive match report"""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    match = models.OneToOneField('matches.Match', on_delete=models.CASCADE, related_name='report')
    referee = models.ForeignKey(Referee, on_delete=models.CASCADE, related_name='reports')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    penalties_not_converted = models.TextField(blank=True)
    serious_incidents = models.TextField(blank=True)
    referee_comments = models.TextField(blank=True)

    match_number = models.CharField(max_length=20, blank=True)
    round_number = models.CharField(max_length=20, blank=True)
    league_level = models.CharField(max_length=50, default="FKF County League")

    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_reports'
    )
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ('submit_match_report', 'Can submit match report'),
            ('approve_match_report', 'Can approve match report'),
            ('reject_match_report', 'Can reject match report'),
        ]

    def __str__(self):
        return f"Report - {self.match} ({self.get_status_display()})"


# ========== MATCHDAY SQUAD MANAGEMENT MODELS ==========

class MatchdaySquad(models.Model):
    """
    Team's submitted matchday squad (25 players: 11 starting + 14 subs)
    Submitted 2 hours before kick-off
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Submission'
        SUBMITTED = 'submitted', 'Submitted - Awaiting Referee Approval'
        APPROVED = 'approved', 'Approved by Referee'
        LOCKED = 'locked', 'Locked (Match Started)'

    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='matchday_squads')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='submitted_squads')

    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey('Referee', on_delete=models.SET_NULL, null=True, related_name='approved_squads')

    locked_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['match', 'team'], name='uniq_matchdaysquad_match_team'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.team.team_name} - {self.match} ({self.get_status_display()})"

    def can_submit(self) -> bool:
        """Squad can be submitted from 4 hours before kick-off while pending."""
        if not self.match.match_date or not self.match.kickoff_time:
            return False
        opens = self.match.kickoff_datetime - timedelta(hours=4)
        return timezone.now() >= opens and self.status == self.Status.PENDING

    def can_edit(self):
        """Squad can be edited before match starts"""
        # Can edit if pending or submitted, or if approved but edit request was granted
        return self.status in ['pending', 'submitted'] and not self.is_locked()

    def can_request_edit(self):
        """Team manager can request edit for approved squad before kick-off"""
        return (self.status == 'approved' and
                not self.is_locked() and
                not self.edit_requests.filter(status='pending').exists())

    def can_view_only(self):
        """Team manager can only view (after kick-off or locked)"""
        return self.status in ['approved', 'locked'] and self.is_locked()

    def is_locked(self) -> bool:
        """Squad is locked once the match has kicked off."""
        if self.status == self.Status.LOCKED:
            return True
        if not self.match.match_date:
            return False
        return timezone.now() >= self.match.kickoff_datetime

    def lock_squad(self) -> bool:
        """Persist the locked state. Returns True if the squad changed."""
        if self.status == self.Status.LOCKED:
            return False
        self.status = self.Status.LOCKED
        self.locked_at = timezone.now()
        self.save(update_fields=['status', 'locked_at', 'updated_at'])
        return True

    def get_starting_eleven(self):
        """Get starting 11 players"""
        return self.squad_players.filter(is_starting=True).order_by('position_order')

    def get_substitutes(self):
        """Get substitute players"""
        return self.squad_players.filter(is_starting=False).order_by('jersey_number')


class SquadEditRequest(models.Model):
    """
    Request from team manager to edit an approved squad before kick-off
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Referee Review'
        APPROVED = 'approved', 'Approved - Can Edit'
        DECLINED = 'declined', 'Declined by Referee'

    squad = models.ForeignKey(MatchdaySquad, on_delete=models.CASCADE, related_name='edit_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='squad_edit_requests')

    # Request details
    reason = models.TextField(help_text="Reason for requesting edit")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Referee response
    reviewed_by = models.ForeignKey('Referee', on_delete=models.SET_NULL, null=True, blank=True)
    review_notes = models.TextField(blank=True, help_text="Referee's review notes")

    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"Edit request for {self.squad} by {self.requested_by.get_full_name()}"

    def approve_request(self, referee, notes=""):
        """Approve the edit request"""
        self.status = 'approved'
        self.reviewed_by = referee
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save()
        # Re-open the squad so the team can edit and resubmit it.
        self.squad.status = MatchdaySquad.Status.SUBMITTED
        self.squad.save(update_fields=['status', 'updated_at'])

    def decline_request(self, referee, notes=""):
        """Decline the edit request"""
        self.status = 'declined'
        self.reviewed_by = referee
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save()


class SquadPlayer(models.Model):
    """
    Individual player in the matchday squad
    """
    squad = models.ForeignKey(MatchdaySquad, on_delete=models.CASCADE, related_name='squad_players')
    player = models.ForeignKey('teams.Player', on_delete=models.CASCADE)

    # Squad position
    is_starting = models.BooleanField(default=False, help_text="Is this player in the starting 11?")
    position_order = models.IntegerField(default=0, help_text="Display order in starting lineup")
    jersey_number = models.IntegerField()

    # Approval tracking
    is_approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['squad', 'player'], name='uniq_squadplayer_squad_player'),
        ]
        ordering = ['-is_starting', 'position_order', 'jersey_number']

    def __str__(self):
        status = "Starting" if self.is_starting else "Substitute"
        return f"{self.player.full_name} #{self.jersey_number} ({status})"

    def clean(self):
        """Validate player selection"""
        # Check if player is suspended
        if self.player.is_suspended:
            raise ValidationError(f"{self.player.full_name} is currently suspended and cannot be selected.")

        # Check if player belongs to the same team
        if self.player.team != self.squad.team:
            raise ValidationError(f"{self.player.full_name} does not belong to {self.squad.team.team_name}.")


class SubstitutionRequest(models.Model):
    """
    In-match substitution request from team manager
    Effected by fourth official/reserve referee
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        COMPLETED = 'completed', 'Completed'

    class SubType(models.TextChoices):
        NORMAL = 'normal', 'Normal Substitution'
        INJURY = 'injury', 'Injury Substitution'
        TACTICAL = 'tactical', 'Tactical Substitution'
        CONCUSSION = 'concussion', 'Concussion Substitution (6th Sub)'

    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='substitution_requests')
    squad = models.ForeignKey(MatchdaySquad, on_delete=models.CASCADE, related_name='substitution_requests')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)

    # Substitution details
    player_out = models.ForeignKey('teams.Player', on_delete=models.CASCADE, related_name='sub_requests_out')
    player_in = models.ForeignKey('teams.Player', on_delete=models.CASCADE, related_name='sub_requests_in')

    minute = models.IntegerField(null=True, blank=True, help_text="Match minute when substitution occurs")
    sub_type = models.CharField(max_length=20, choices=SubType.choices, default=SubType.NORMAL)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Request tracking
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sub_requests')

    # Approval tracking
    effected_at = models.DateTimeField(null=True, blank=True)
    effected_by = models.ForeignKey('Referee', on_delete=models.SET_NULL, null=True, related_name='effected_subs')

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['minute', 'requested_at']

    def __str__(self):
        return f"{self.minute}' - {self.player_out.full_name} → {self.player_in.full_name}"

    def clean(self):
        """Validate substitution request"""
        # Check player_out is in starting lineup or has been subbed in
        if not self.squad.squad_players.filter(player=self.player_out).exists():
            raise ValidationError(f"{self.player_out.full_name} is not in the matchday squad.")

        # Check player_in is on the bench
        squad_player_in = self.squad.squad_players.filter(player=self.player_in).first()
        if not squad_player_in or squad_player_in.is_starting:
            raise ValidationError(f"{self.player_in.full_name} is not available as a substitute.")

        # Check substitution limits (max 5 normal subs)
        if self.sub_type == 'normal':
            team_subs = SubstitutionRequest.objects.filter(
                match=self.match,
                team=self.team,
                status='completed',
                sub_type='normal'
            ).count()

            if team_subs >= 5:
                raise ValidationError("Maximum of 5 substitutions already used.")

        # Concussion sub is independent (6th sub)
        if self.sub_type == 'concussion':
            concussion_subs = SubstitutionRequest.objects.filter(
                match=self.match,
                team=self.team,
                status='completed',
                sub_type='concussion'
            ).count()

            if concussion_subs >= 1:
                raise ValidationError("Concussion substitution already used.")


class SubstitutionOpportunity(models.Model):
    """
    Track substitution opportunities (max 3 opportunities, excluding halftime)
    """
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='sub_opportunities')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)

    opportunity_number = models.IntegerField(help_text="1st, 2nd, or 3rd opportunity")
    minute = models.IntegerField()
    is_halftime = models.BooleanField(default=False, help_text="Halftime subs don't count toward 3 opportunities")

    # Track which substitutions were made in this opportunity
    substitutions = models.ManyToManyField(SubstitutionRequest, related_name='opportunities')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['match', 'team', 'opportunity_number'], name='uniq_subopportunity_number',
            ),
        ]
        ordering = ['minute']

    def __str__(self):
        return f"{self.team.team_name} - Opportunity {self.opportunity_number} ({self.minute}')"

    def clean(self):
        """Validate opportunity limits"""
        if not self.is_halftime:
            opportunities = SubstitutionOpportunity.objects.filter(
                match=self.match,
                team=self.team,
                is_halftime=False
            ).count()

            if opportunities >= 3 and not self.pk:
                raise ValidationError("Maximum of 3 substitution opportunities (excluding halftime) already used.")