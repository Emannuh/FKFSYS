# teams/models.py
from django.db import models
from django.utils import timezone
import uuid

class Zone(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']

class Team(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    
    # Team Information
    team_name = models.CharField(max_length=200)
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
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    
    # League Details
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment Information
    payment_status = models.BooleanField(default=False)
    payment_date = models.DateField(blank=True, null=True)
    
    # Timestamps
    registration_date = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.team_code:
            # Generate team code: T + first 3 letters + random numbers
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
    
    def __str__(self):
        return self.full_name
    
    class Meta:
        ordering = ['team', 'jersey_number']
        unique_together = ['team', 'jersey_number']