# referees/models.py - COMPLETE AND UPDATED VERSION
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from fkf_league.validators import validate_kenya_phone
from fkf_league.constants import KENYA_COUNTIES
from datetime import timedelta
import random
import string


class Referee(models.Model):
    """
    Referee model - Simple registration with approval workflow
    """
    LEVEL_CHOICES = [
        ('fifa_elite', 'FIFA Elite'),
        ('fkf_premier', 'FKF Premier League'),
        ('fkf_national_super', 'FKF National Super League'),
        ('fkf_division_1', 'FKF Division 1'),
        ('fkf_division_2', 'FKF Division 2'),
        ('fkf_county', 'FKF County League'),
        ('grassroot', 'Grassroot'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    
    SPECIALIZATION_CHOICES = [
        ('REFEREE', 'Referee'),
        ('ASSISTANT_REFEREE', 'Assistant Referee'),
        ('MATCH_COMMISSIONER', 'Match Commissioner'),
    ]
    
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
    photo = models.ImageField(upload_to='referee_photos/', blank=True, null=True)
    
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
        choices=LEVEL_CHOICES,
        blank=True,
        null=True,
        verbose_name="Referee Level"
    )
    specialization = models.CharField(
        max_length=30,
        choices=SPECIALIZATION_CHOICES,
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
        choices=STATUS_CHOICES, 
        default='pending'
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
        # ✅ ADD THIS - Permissions for referee management
        permissions = [
            ('manage_referees', 'Can manage referees (approve/reject/suspend)'),
        ]
    
    def __str__(self):
        return f"{self.full_name} - {self.unique_id or 'Pending'}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def generate_unique_id(self):
        """Generate unique referee ID: REF-YYYY-XXXX"""
        while True:
            year = timezone.now().year
            random_num = ''.join(random.choices(string.digits, k=4))
            unique_id = f"REF-{year}-{random_num}"
            
            if not Referee.objects.filter(unique_id=unique_id).exists():
                return unique_id
    
    def approve(self, approved_by_user):
        """
        Approve referee and create user account
        Returns: (unique_id, default_password)
        """
        if not self.unique_id:
            self.unique_id = self.generate_unique_id()
        
        default_password = "Referee@2024"
        
        if not self.user:
            user = User.objects.create_user(
                username=self.unique_id,
                email=self.email,
                first_name=self.first_name,
                last_name=self.last_name,
                password=default_password
            )
            self.user = user
        
        self.status = 'approved'
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.rejection_reason = ''
        self.is_active = True
        self.save()
        
        return self.unique_id, default_password
    
    def reject(self, reason=''):
        """Reject registration"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.is_active = False
        self.save()
    
    def suspend(self, reason=''):
        """Suspend active referee"""
        self.status = 'suspended'
        self.suspension_reason = reason
        self.is_active = False
        self.save()
    
    def reactivate(self):
        """Reactivate suspended referee"""
        if self.status == 'approved':
            self.is_active = True
            self.suspension_reason = ''
            self.save()
    
    def can_be_appointed(self):
        """Check if referee can be appointed"""
        return self.status == 'approved' and self.is_active
    
    def can_be_appointed_as(self, role):
        """
        Check if referee can be appointed to a specific role based on specialization
        
        Rules:
        - REFEREE can be: REFEREE, RESERVE, VAR, AR2 (if needed)
        - ASSISTANT_REFEREE can be: AR1, AR2, FOURTH, AVAR1
        - MATCH_COMMISSIONER can only be: COMMISSIONER
        """
        if not self.can_be_appointed():
            return False
        
        if not self.specialization:
            # If no specialization set, allow all roles (backward compatibility)
            return True
        
        role_mapping = {
            'REFEREE': ['REFEREE', 'RESERVE', 'VAR'],
            'ASSISTANT_REFEREE': ['AR1', 'AR2', 'RESERVE', 'AVAR1', 'RESERVE_AR'],
            'MATCH_COMMISSIONER': ['COMMISSIONER'],
        }
        
        # AVAR2 can be either REFEREE or ASSISTANT_REFEREE
        if role == 'AVAR2':
            return self.specialization in ['REFEREE', 'ASSISTANT_REFEREE']
        
        return role in role_mapping.get(self.specialization, [])


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
        unique_together = ['referee', 'date']
        verbose_name_plural = 'Referee Availabilities'
        ordering = ['-date']
    
    def __str__(self):
        status = "Available" if self.is_available else "Unavailable"
        return f"{self.referee.full_name} - {self.date} ({status})"


class MatchOfficials(models.Model):
    """
    Match officials with enhanced validation
    """
    OFFICIAL_ROLES = [
        ('REFEREE', 'Referee'),
        ('AR1', 'Assistant Referee 1'),
        ('AR2', 'Assistant Referee 2'),
        ('RESERVE', 'Reserve Referee'),
        ('RESERVE_AR', 'Reserve Assistant Referee'),
        ('VAR', 'Video Assistant Referee'),
        ('AVAR1', 'Assistant VAR 1'),
        ('AVAR2', 'Assistant VAR 2'),
        ('COMMISSIONER', 'Match Commissioner'),
    ]
    
    APPOINTMENT_STATUS = [
        ('PENDING', 'Pending Appointment'),
        ('APPOINTED', 'Appointed - Awaiting Confirmation'),
        ('CONFIRMED', 'Confirmed by All'),
        ('REJECTED', 'Some Officials Rejected'),
        ('ALTERNATE', 'Using Alternate Officials'),
        ('COMPLETED', 'Match Completed'),
        ('CANCELLED', 'Match Cancelled'),
    ]
    
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
        choices=APPOINTMENT_STATUS, 
        default='PENDING'
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
        """
        ENHANCED VALIDATION - Combines both documents
        """
        # Rule 1: 4-day appointment window (from both)
        if self.match and self.match.match_date:
            days_until_match = (self.match.match_date.date() - timezone.now().date()).days
            if days_until_match > 4 and self.status == 'APPOINTED':
                raise ValidationError(
                    f"Cannot appoint referees yet. Match is in {days_until_match} days. "
                    f"Appointments can only be made within 4 days of match."
                )
        
        # Rule 2: Round sequencing - Must complete appointments for previous round first
        if self.match and hasattr(self.match, 'round_number') and self.match.round_number > 1:
            from matches.models import Match
            previous_round = self.match.round_number - 1
            
            # Get all matches from previous round in same zone
            previous_round_matches = Match.objects.filter(
                zone=self.match.zone,
                round_number=previous_round
            ).exclude(status__in=['cancelled', 'postponed'])
            
            # Check if all previous round matches have officials appointed
            if previous_round_matches.exists():
                unappointed_matches = []
                for prev_match in previous_round_matches:
                    if not hasattr(prev_match, 'officials') or prev_match.officials is None:
                        unappointed_matches.append(prev_match)
                
                if unappointed_matches:
                    match_info = [f"{m.home_team} vs {m.away_team}" for m in unappointed_matches[:3]]
                    raise ValidationError(
                        f"Cannot appoint for Round {self.match.round_number} yet. "
                        f"Complete all appointments for Round {previous_round} first. "
                        f"Unappointed matches: {', '.join(match_info)}"
                        f"{' and more...' if len(unappointed_matches) > 3 else ''}"
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
        
        if self.status == 'APPOINTED' and not self.appointment_made_at:
            self.appointment_made_at = timezone.now()
        
        # Check if all required officials confirmed
        if self.main_confirmed and self.ar1_confirmed and self.ar2_confirmed:
            if self.status == 'APPOINTED':
                self.status = 'CONFIRMED'
        
        if validate:
            self.full_clean()
        
        super().save(*args, **kwargs)
    
    @property
    def can_appoint(self):
        """Check if appointment can be made"""
        if not self.match or not self.match.match_date:
            return False
        days_until_match = (self.match.match_date.date() - timezone.now().date()).days
        return days_until_match <= 4
    
    @property
    def all_required_confirmed(self):
        """Check if all required officials have confirmed"""
        return (
            (not self.main_referee or self.main_confirmed) and
            (not self.assistant_1 or self.ar1_confirmed) and
            (not self.assistant_2 or self.ar2_confirmed)
        )
    
    @property
    def required_officials_appointed(self):
        """Check if all required officials are appointed"""
        return bool(self.main_referee and self.assistant_1 and self.assistant_2)
    
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
    
    def get_appointed_officials_list(self):
        """Get list of all appointed officials - UPDATED FOR OFFICIAL_ROLES"""
        officials_list = []
        
        # Map to OFFICIAL_ROLES format
        role_mapping = {
            'main_referee': ('REFEREE', 'Referee', self.main_confirmed),
            'assistant_1': ('AR1', 'Assistant Referee 1', self.ar1_confirmed),
            'assistant_2': ('AR2', 'Assistant Referee 2', self.ar2_confirmed),
            'reserve_referee': ('RESERVE', 'Reserve Referee', self.reserve_confirmed),
            'reserve_assistant': ('RESERVE_AR', 'Reserve Assistant Referee', False),
            'var': ('VAR', 'Video Assistant Referee', self.var_confirmed),
            'avar1': ('AVAR1', 'Assistant VAR 1', False),
            'fourth_official': ('RESERVE', 'Reserve Referee', self.fourth_confirmed),
            'match_commissioner': ('COMMISSIONER', 'Match Commissioner', False),
        }
        
        for field, (role_code, role_name, confirmed) in role_mapping.items():
            referee = getattr(self, field)
            if referee:
                officials_list.append({
                    'role_code': role_code,
                    'role_name': role_name,
                    'referee': referee,
                    'confirmed': confirmed
                })
        
        return officials_list
    
    def get_referee_role(self, referee):
        """Get role of a specific referee in this match"""
        if self.main_referee == referee:
            return 'REFEREE'
        elif self.assistant_1 == referee:
            return 'AR1'
        elif self.assistant_2 == referee:
            return 'AR2'
        elif self.fourth_official == referee:
            return 'RESERVE'
        elif self.reserve_referee == referee:
            return 'RESERVE'
        elif self.var == referee:
            return 'VAR'
        elif self.avar1 == referee:
            return 'AVAR1'
        elif self.match_commissioner == referee:
            return 'COMMISSIONER'
        elif self.reserve_assistant == referee:
            return 'RESERVE_AR'
        return None


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
        unique_together = ['match', 'team', 'item']
    
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
        unique_together = ['match', 'team', 'player']
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
        unique_together = ['match', 'team', 'player']
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
    GOAL_TYPE_CHOICES = [
        ('normal', 'Normal Goal'),
        ('penalty', 'Penalty'),
        ('own_goal', 'Own Goal'),
        ('free_kick', 'Free Kick'),
    ]
    
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
    goal_type = models.CharField(max_length=20, choices=GOAL_TYPE_CHOICES, default='normal')
    jersey_number = models.IntegerField()
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['minute']
    
    def __str__(self):
        return f"{self.minute}' - {self.player} ({self.team})"


class PreMatchMeetingForm(models.Model):
    """Pre-match meeting form - filled by main referee 36 hours before match"""
    STATUS_CHOICES = [
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted - Awaiting League Admin Approval'),
        ('admin_approved', 'Admin Approved - Awaiting Referee Manager Approval'),
        ('approved', 'Fully Approved'),
        ('rejected', 'Rejected'),
    ]
    
    match = models.OneToOneField('matches.Match', on_delete=models.CASCADE, related_name='pre_match_form')
    referee = models.ForeignKey(Referee, on_delete=models.CASCADE, related_name='pre_match_forms')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    
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
    
    def can_be_filled(self):
        """Check if form can be filled (36 hours before match)"""
        if self.is_locked:
            return False
        time_until_match = self.match.match_date - timezone.now()
        return timedelta(hours=0) <= time_until_match <= timedelta(hours=36)
    
    def can_be_edited(self):
        """Check if form can be edited (before match only)"""
        if self.is_locked:
            return False
        return timezone.now() < self.match.match_date
    
    def lock_form(self):
        """Lock form after match"""
        if timezone.now() >= self.match.match_date:
            self.is_locked = True
            self.save()


class MatchReport(models.Model):
    """Comprehensive match report"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    match = models.OneToOneField('matches.Match', on_delete=models.CASCADE, related_name='report')
    referee = models.ForeignKey(Referee, on_delete=models.CASCADE, related_name='reports')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # ✅ THESE PERMISSIONS ARE CORRECT - Keep them
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
    STATUS_CHOICES = [
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted - Awaiting Referee Approval'),
        ('approved', 'Approved by Referee'),
        ('locked', 'Locked (Match Started)'),
    ]
    
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='matchday_squads')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
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
        unique_together = ['match', 'team']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.team.name} - {self.match} ({self.get_status_display()})"
    
    def can_submit(self):
        """Check if squad can be submitted (4 hours before kick-off)"""
        if not self.match.match_date or not self.match.kickoff_time:
            return False
        
        try:
            # Handle kickoff_time as either time object or string
            if isinstance(self.match.kickoff_time, str):
                kickoff_time = timezone.datetime.strptime(self.match.kickoff_time, '%H:%M').time()
            else:
                kickoff_time = self.match.kickoff_time
            
            match_datetime = timezone.make_aware(
                timezone.datetime.combine(self.match.match_date, kickoff_time)
            )
            submission_time = match_datetime - timedelta(hours=4)
            
            return timezone.now() >= submission_time and self.status == 'pending'
        except (ValueError, TypeError, AttributeError):
            return False
    
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
    
    def is_locked(self):
        """Squad is locked at kick-off time"""
        if self.status == 'locked':
            return True
        
        if not self.match.match_date or not self.match.kickoff_time:
            return False
        
        try:
            # Handle kickoff_time as either time object or string
            if isinstance(self.match.kickoff_time, str):
                kickoff_time = timezone.datetime.strptime(self.match.kickoff_time, '%H:%M').time()
            else:
                kickoff_time = self.match.kickoff_time
            
            # Extract date from match_date (which is a datetime) and combine with kickoff_time
            match_date = self.match.match_date.date()
            match_datetime_naive = timezone.datetime.combine(match_date, kickoff_time)
            
            # Make it aware in local timezone, then convert to UTC for comparison with timezone.now()
            match_datetime_local = timezone.make_aware(match_datetime_naive)
            match_datetime_utc = match_datetime_local.astimezone(timezone.utc)
            
            return timezone.now() >= match_datetime_utc
        except (ValueError, TypeError, AttributeError):
            return False
    
    def lock_squad(self):
        """Lock squad at kick-off"""
        if not self.is_locked():
            self.status = 'locked'
            self.locked_at = timezone.now()
            self.save()
    
    def get_starting_eleven(self):
        """Get starting 11 players"""
        return self.squad_players.filter(is_starting=True).order_by('position_order')
    
    def get_substitutes(self):
        """Get substitute players"""
        return self.squad_players.filter(is_starting=False).order_by('jersey_number')
    
    def validate_squad(self):
        """Validate squad meets all requirements"""
        starting = self.squad_players.filter(is_starting=True)
        subs = self.squad_players.filter(is_starting=False)
        
        # Must have 11 starting players
        if starting.count() != 11:
            raise ValidationError(f"Must have exactly 11 starting players. Currently have {starting.count()}.")
        
        # Must have exactly 14 substitutes
        if subs.count() != 14:
            raise ValidationError(f"Must have exactly 14 substitute players. Currently have {subs.count()}.")
        
        # Starting 11 must include at least 1 goalkeeper
        starting_gks = starting.filter(player__position='GK').count()
        if starting_gks < 1:
            raise ValidationError("Starting lineup must include at least 1 goalkeeper.")
        
        # Substitutes must include at least 1 goalkeeper
        sub_gks = subs.filter(player__position='GK').count()
        if sub_gks < 1:
            raise ValidationError("Substitutes must include at least 1 goalkeeper.")
        
        # Check for suspended players
        suspended = self.squad_players.filter(player__is_suspended=True)
        if suspended.exists():
            player_names = ", ".join([sp.player.full_name for sp in suspended])
            raise ValidationError(f"Cannot include suspended players: {player_names}")
        
        return True


class SquadEditRequest(models.Model):
    """
    Request from team manager to edit an approved squad before kick-off
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Referee Review'),
        ('approved', 'Approved - Can Edit'),
        ('declined', 'Declined by Referee'),
    ]
    
    squad = models.ForeignKey(MatchdaySquad, on_delete=models.CASCADE, related_name='edit_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='squad_edit_requests')
    
    # Request details
    reason = models.TextField(help_text="Reason for requesting edit")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
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
    
    def can_request_edit(self):
        """Check if edit can be requested (approved squad, before kick-off, no pending request)"""
        if self.squad.status != 'approved':
            return False
        
        # Check if match hasn't started
        if self.squad.is_locked():
            return False
        
        # Check no pending request exists
        return not SquadEditRequest.objects.filter(
            squad=self.squad, 
            status='pending'
        ).exists()
    
    def approve_request(self, referee, notes=""):
        """Approve the edit request"""
        self.status = 'approved'
        self.reviewed_by = referee
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save()
        
        # Unlock the squad for editing
        self.squad.status = 'submitted'  # Allow editing
        self.squad.save()
    
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
        unique_together = ['squad', 'player']
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
            raise ValidationError(f"{self.player.full_name} does not belong to {self.squad.team.name}.")


class SubstitutionRequest(models.Model):
    """
    In-match substitution request from team manager
    Effected by fourth official/reserve referee
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    
    SUB_TYPE_CHOICES = [
        ('normal', 'Normal Substitution'),
        ('injury', 'Injury Substitution'),
        ('tactical', 'Tactical Substitution'),
        ('concussion', 'Concussion Substitution (6th Sub)'),
    ]
    
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='substitution_requests')
    squad = models.ForeignKey(MatchdaySquad, on_delete=models.CASCADE, related_name='substitution_requests')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    
    # Substitution details
    player_out = models.ForeignKey('teams.Player', on_delete=models.CASCADE, related_name='sub_requests_out')
    player_in = models.ForeignKey('teams.Player', on_delete=models.CASCADE, related_name='sub_requests_in')
    
    minute = models.IntegerField(null=True, blank=True, help_text="Match minute when substitution occurs")
    sub_type = models.CharField(max_length=20, choices=SUB_TYPE_CHOICES, default='normal')
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
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
        unique_together = ['match', 'team', 'opportunity_number']
        ordering = ['minute']
    
    def __str__(self):
        return f"{self.team.name} - Opportunity {self.opportunity_number} ({self.minute}')"
    
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