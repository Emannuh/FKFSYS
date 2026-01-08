from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid

class Zone(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Fixture generation fields
    fixtures_generated = models.BooleanField(default=False)
    fixture_generation_date = models.DateTimeField(null=True, blank=True)
    season_start_date = models.DateField(null=True, blank=True)
    match_day_of_week = models.IntegerField(default=6, choices=[(6, 'Saturday'), (0, 'Sunday')])
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
    
    @property
    def approved_teams_count(self):
        return self.team_set.filter(status='approved').count()


class Team(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    
    # Team Information
    team_name = models.CharField(max_length=200, unique=True)
    team_code = models.CharField(max_length=20, unique=True, blank=True)
    logo = models.ImageField(upload_to='team_logos/', blank=True, null=True)
    
    # Location Details
    location = models.CharField(max_length=200)
    home_ground = models.CharField(max_length=200)
    map_location = models.URLField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    
    # Contact Information
    contact_person = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, unique=True)
    
    # League Details
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Team Manager
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_teams'
    )
    
    # Payment Information
    payment_status = models.BooleanField(default=False)
    payment_date = models.DateField(blank=True, null=True)
    
    # Home Kit
    home_jersey_color = models.CharField(max_length=50, blank=True, default='#dc3545')
    home_shorts_color = models.CharField(max_length=50, blank=True, default='#ffffff')
    home_socks_color = models.CharField(max_length=50, blank=True, default='#dc3545')
    
    # Away Kit
    away_jersey_color = models.CharField(max_length=50, blank=True, default='#ffffff')
    away_shorts_color = models.CharField(max_length=50, blank=True, default='#dc3545')
    away_socks_color = models.CharField(max_length=50, blank=True, default='#ffffff')
    
    # Third Kit (Optional)
    third_jersey_color = models.CharField(max_length=50, blank=True)
    third_shorts_color = models.CharField(max_length=50, blank=True)
    third_socks_color = models.CharField(max_length=50, blank=True)
    
    # Goalkeeper Home Kit
    gk_home_jersey_color = models.CharField(max_length=50, blank=True, default='#28a745')
    gk_home_shorts_color = models.CharField(max_length=50, blank=True, default='#28a745')
    gk_home_socks_color = models.CharField(max_length=50, blank=True, default='#28a745')
    
    # Goalkeeper Away Kit
    gk_away_jersey_color = models.CharField(max_length=50, blank=True, default='#ffc107')
    gk_away_shorts_color = models.CharField(max_length=50, blank=True, default='#ffc107')
    gk_away_socks_color = models.CharField(max_length=50, blank=True, default='#ffc107')
    
    # Goalkeeper Third Kit
    gk_third_jersey_color = models.CharField(max_length=50, blank=True)
    gk_third_shorts_color = models.CharField(max_length=50, blank=True)
    gk_third_socks_color = models.CharField(max_length=50, blank=True)
    
    # Kit completion tracking
    kit_colors_set = models.BooleanField(default=False)
    kit_setup_prompt_shown = models.BooleanField(default=False)
    
    # Home Kit Images
    home_kit_image = models.ImageField(upload_to='kit_images/', blank=True, null=True, 
                                      help_text="Upload home kit design/image")
    # Away Kit Images
    away_kit_image = models.ImageField(upload_to='kit_images/', blank=True, null=True, 
                                      help_text="Upload away kit design/image")
    # Third Kit Images (Optional)
    third_kit_image = models.ImageField(upload_to='kit_images/', blank=True, null=True, 
                                       help_text="Upload third kit design/image")
    # GK Home Kit Images
    gk_home_kit_image = models.ImageField(upload_to='kit_images/', blank=True, null=True, 
                                         help_text="Upload GK home kit design/image")
    # GK Away Kit Images
    gk_away_kit_image = models.ImageField(upload_to='kit_images/', blank=True, null=True, 
                                         help_text="Upload GK away kit design/image")
    # GK Third Kit Images (Optional)
    gk_third_kit_image = models.ImageField(upload_to='kit_images/', blank=True, null=True, 
                                          help_text="Upload GK third kit design/image")
    
    # Timestamps
    registration_date = models.DateTimeField(auto_now_add=True)
    
    
    def save(self, *args, **kwargs):
        if not self.team_code:
            prefix = self.team_name[:3].upper()
            self.team_code = f"T{prefix}{uuid.uuid4().hex[:4].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.team_name
    
    class Meta:
        ordering = ['team_name']


class Player(models.Model):
    POSITION_CHOICES = [
        ('GK', 'Goalkeeper'),
        ('DF', 'Defender'),
        ('MF', 'Midfielder'),
        ('FW', 'Forward'),
    ]
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100, default='Kenyan')
    id_number = models.CharField(max_length=20, unique=True)
    photo = models.ImageField(upload_to='player_photos/', blank=True, null=True)
    
    # FKF License Information
    fkf_license_number = models.CharField(max_length=50, blank=True, verbose_name="FKF License Number")
    license_expiry_date = models.DateField(blank=True, null=True, verbose_name="License Expiry Date")
    
    # Team Information
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    position = models.CharField(max_length=2, choices=POSITION_CHOICES)
    jersey_number = models.IntegerField()
    is_captain = models.BooleanField(default=False)
    
    # Statistics
    yellow_cards = models.IntegerField(default=0)
    red_cards = models.IntegerField(default=0)
    goals_scored = models.IntegerField(default=0)
    matches_played = models.IntegerField(default=0)
    
    # Suspension
    is_suspended = models.BooleanField(default=False)
    suspension_end = models.DateField(blank=True, null=True)
    suspension_reason = models.TextField(blank=True)
    
    # Timestamps
    registration_date = models.DateTimeField(auto_now_add=True)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
    
    def __str__(self):
        return self.full_name
    
    class Meta:
        ordering = ['team', 'jersey_number']
        unique_together = ['team', 'jersey_number']


class LeagueSettings(models.Model):
    """Singleton model for league-wide settings"""
    
    # Registration Windows
    team_registration_open = models.BooleanField(
        default=True, 
        help_text="Allow new teams to register"
    )
    player_registration_open = models.BooleanField(
        default=True, 
        help_text="Allow teams to add new players"
    )
    transfer_window_open = models.BooleanField(
        default=True, 
        help_text="Allow teams to request player transfers"
    )

    # Registration / transfer deadlines
    team_registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Automatically close team registration at this date/time"
    )
    player_registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Automatically close player registration at this date/time"
    )
    transfer_window_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Automatically close transfer window at this date/time"
    )
    
    # Closed dates (when manually closed by admin)
    team_registration_closed_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date/time when team registration was closed"
    )
    player_registration_closed_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date/time when player registration was closed"
    )
    transfer_window_closed_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date/time when transfer window was closed"
    )
    
    # Meta information
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='league_settings_updates'
    )
    
    class Meta:
        verbose_name = "League Settings"
        verbose_name_plural = "League Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        
        # Record closure dates when windows are manually closed
        # Only process if update_fields doesn't exist or includes the open fields
        update_fields = kwargs.get('update_fields', None)
        process_closure_dates = (
            update_fields is None or 
            'team_registration_open' in update_fields or
            'player_registration_open' in update_fields or
            'transfer_window_open' in update_fields
        )
        
        if self.pk and process_closure_dates:
            try:
                old_instance = LeagueSettings.objects.get(pk=self.pk)
                now = timezone.now()
                
                # Team registration closed
                if old_instance.team_registration_open and not self.team_registration_open:
                    self.team_registration_closed_date = now
                    if update_fields and 'team_registration_closed_date' not in update_fields:
                        update_fields = list(update_fields) + ['team_registration_closed_date']
                        kwargs['update_fields'] = update_fields
                # Team registration reopened
                elif not old_instance.team_registration_open and self.team_registration_open:
                    self.team_registration_closed_date = None
                    if update_fields and 'team_registration_closed_date' not in update_fields:
                        update_fields = list(update_fields) + ['team_registration_closed_date']
                        kwargs['update_fields'] = update_fields
                
                # Player registration closed
                if old_instance.player_registration_open and not self.player_registration_open:
                    self.player_registration_closed_date = now
                    if update_fields and 'player_registration_closed_date' not in update_fields:
                        update_fields = list(update_fields) + ['player_registration_closed_date']
                        kwargs['update_fields'] = update_fields
                # Player registration reopened
                elif not old_instance.player_registration_open and self.player_registration_open:
                    self.player_registration_closed_date = None
                    if update_fields and 'player_registration_closed_date' not in update_fields:
                        update_fields = list(update_fields) + ['player_registration_closed_date']
                        kwargs['update_fields'] = update_fields
                
                # Transfer window closed
                if old_instance.transfer_window_open and not self.transfer_window_open:
                    self.transfer_window_closed_date = now
                    if update_fields and 'transfer_window_closed_date' not in update_fields:
                        update_fields = list(update_fields) + ['transfer_window_closed_date']
                        kwargs['update_fields'] = update_fields
                # Transfer window reopened
                elif not old_instance.transfer_window_open and self.transfer_window_open:
                    self.transfer_window_closed_date = None
                    if update_fields and 'transfer_window_closed_date' not in update_fields:
                        update_fields = list(update_fields) + ['transfer_window_closed_date']
                        kwargs['update_fields'] = update_fields
            except LeagueSettings.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Prevent deletion
        pass
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        # Refresh from database to avoid stale data
        if not created:
            settings.refresh_from_db()
        settings._auto_close_by_deadline()
        return settings

    def _auto_close_by_deadline(self):
        """Auto-close windows when deadlines pass"""
        now = timezone.now()
        updated = False
        update_fields = ['updated_at']

        if self.team_registration_deadline and self.team_registration_open:
            if now >= self.team_registration_deadline:
                self.team_registration_open = False
                self.team_registration_closed_date = self.team_registration_deadline
                update_fields.extend(['team_registration_open', 'team_registration_closed_date'])
                updated = True

        if self.player_registration_deadline and self.player_registration_open:
            if now >= self.player_registration_deadline:
                self.player_registration_open = False
                self.player_registration_closed_date = self.player_registration_deadline
                update_fields.extend(['player_registration_open', 'player_registration_closed_date'])
                updated = True

        if self.transfer_window_deadline and self.transfer_window_open:
            if now >= self.transfer_window_deadline:
                self.transfer_window_open = False
                self.transfer_window_closed_date = self.transfer_window_deadline
                update_fields.extend(['transfer_window_open', 'transfer_window_closed_date'])
                updated = True

        if updated:
            self.save(update_fields=update_fields)
    
    def __str__(self):
        return "League Settings"


class TeamOfficial(models.Model):
    """Model for team officials (coaches, doctor, patron)"""
    
    POSITION_CHOICES = [
        ('head_coach', 'Head Coach'),
        ('assistant_coach', 'Assistant Coach'),
        ('goalkeeper_coach', 'Goalkeeper Coach'),
        ('team_doctor', 'Team Doctor'),
        ('team_patron', 'Team Patron'),
    ]
    
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='officials'
    )
    position = models.CharField(max_length=20, choices=POSITION_CHOICES)
    full_name = models.CharField(max_length=200)
    id_number = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=20)
    
    # CAF License (only for coaches)
    caf_license_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="CAF License Number",
        help_text="Required for coaches"
    )
    license_expiry_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="License Expiry Date"
    )
    
    photo = models.ImageField(
        upload_to='official_photos/',
        blank=True,
        null=True
    )
    
    registration_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['team', 'position']
        unique_together = ['team', 'position']
    
    def __str__(self):
        return f"{self.full_name} - {self.get_position_display()} ({self.team.team_name})"


class TransferRequest(models.Model):
    """Model for tracking player transfer requests between teams"""
    
    STATUS_CHOICES = [
        ('pending_parent', 'Pending Parent Club Decision'),
        ('approved', 'Approved - Transfer Complete'),
        ('rejected', 'Rejected by Parent Club'),
        ('cancelled', 'Cancelled by Requester'),
    ]
    
    # Transfer Details
    player = models.ForeignKey(
        'Player',
        on_delete=models.CASCADE,
        related_name='transfer_requests'
    )
    from_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='outgoing_transfer_requests',
        help_text="Current team (parent club)"
    )
    to_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='incoming_transfer_requests',
        help_text="Requesting team"
    )
    
    # Request Information
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending_parent'
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='transfer_requests_made'
    )
    request_date = models.DateTimeField(auto_now_add=True)
    
    # Parent Club Decision
    parent_decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfer_decisions_made'
    )
    parent_decision_reason = models.TextField(blank=True)
    parent_decision_date = models.DateTimeField(null=True, blank=True)
    
    # Admin Override
    admin_override = models.BooleanField(
        default=False,
        help_text="True if admin forced approval after rejection"
    )
    admin_override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfer_overrides_made'
    )
    admin_override_reason = models.TextField(blank=True)
    admin_override_date = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['status', 'from_team']),
            models.Index(fields=['status', 'to_team']),
            models.Index(fields=['player', 'status']),
        ]
    
    def clean(self):
        """Validate transfer request"""
        if self.from_team == self.to_team:
            raise ValidationError("Cannot transfer player to the same team")
        
        # Check for duplicate pending requests
        if not self.pk:  # Only on creation
            duplicate = TransferRequest.objects.filter(
                player=self.player,
                to_team=self.to_team,
                status='pending_parent'
            ).exists()
            if duplicate:
                raise ValidationError(
                    f"A pending transfer request already exists for {self.player} to {self.to_team}"
                )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def approve_by_parent(self, user, execute_transfer=True):
        """Parent club approves the transfer"""
        self.status = 'approved'
        self.parent_decision_by = user
        self.parent_decision_date = timezone.now()
        self.save()
        
        if execute_transfer:
            self.execute_transfer()
    
    def reject_by_parent(self, user, reason):
        """Parent club rejects the transfer"""
        self.status = 'rejected'
        self.parent_decision_by = user
        self.parent_decision_reason = reason
        self.parent_decision_date = timezone.now()
        self.save()
    
    def override_by_admin(self, user, reason):
        """Admin overrides rejection and forces transfer"""
        self.status = 'approved'
        self.admin_override = True
        self.admin_override_by = user
        self.admin_override_reason = reason
        self.admin_override_date = timezone.now()
        self.save()
        
        self.execute_transfer()
    
    def cancel_by_requester(self):
        """Requester cancels the transfer request"""
        if self.status == 'pending_parent':
            self.status = 'cancelled'
            self.save()
            return True
        return False
    
    def execute_transfer(self):
        """Execute the actual player transfer"""
        if self.status == 'approved':
            # Transfer the player
            self.player.team = self.to_team
            self.player.save()
            
            # Log transfer history
            TransferHistory.objects.create(
                transfer_request=self,
                player=self.player,
                from_team=self.from_team,
                to_team=self.to_team,
                approved_by=self.parent_decision_by,
                admin_override=self.admin_override
            )
    
    def __str__(self):
        return f"{self.player}: {self.from_team} → {self.to_team} ({self.get_status_display()})"


class TransferHistory(models.Model):
    """Historical record of completed transfers"""
    
    transfer_request = models.OneToOneField(
        TransferRequest,
        on_delete=models.CASCADE,
        related_name='history'
    )
    player = models.ForeignKey(
        'Player',
        on_delete=models.CASCADE,
        related_name='transfer_history'
    )
    from_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='players_transferred_out'
    )
    to_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='players_transferred_in'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    admin_override = models.BooleanField(default=False)
    transfer_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Transfer History"
        verbose_name_plural = "Transfer Histories"
        ordering = ['-transfer_date']
    
    def __str__(self):
        return f"{self.player} transferred from {self.from_team} to {self.to_team} on {self.transfer_date.date()}"
