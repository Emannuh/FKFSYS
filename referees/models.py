# referees/models.py - COMPLETE AND UPDATED VERSION
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
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
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Phone Number")
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
    county = models.CharField(max_length=100, blank=True, null=True)
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
        ('FOURTH', 'Fourth Official'),
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
    ar1_confirmed = models.BooleanField(default=False)
    ar1_confirmed_at = models.DateTimeField(null=True, blank=True)
    ar2_confirmed = models.BooleanField(default=False)
    ar2_confirmed_at = models.DateTimeField(null=True, blank=True)
    reserve_confirmed = models.BooleanField(default=False)
    var_confirmed = models.BooleanField(default=False)
    fourth_confirmed = models.BooleanField(default=False)
    
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
        
        # Rule 2: Round sequencing (from Document 2)
        if self.match and hasattr(self.match, 'round_number'):
            from matches.models import Match
            previous_matches = Match.objects.filter(
                zone=self.match.zone,
                round_number=self.match.round_number,
                match_date__lt=self.match.match_date
            ).exclude(status__in=['completed', 'cancelled', 'postponed'])
            
            if previous_matches.exists():
                match_dates = [m.match_date.strftime("%b %d") for m in previous_matches]
                raise ValidationError(
                    f"Cannot appoint for this match yet. "
                    f"Previous matches in round {self.match.round_number} not completed: "
                    f"{', '.join(match_dates)}"
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
            (self.fourth_official, 'Fourth Official'),
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
            'fourth_official': ('FOURTH', 'Fourth Official', self.fourth_confirmed),
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
            return 'FOURTH'
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