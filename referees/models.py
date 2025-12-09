from django.db import models
from django.contrib.auth.models import User

class Referee(models.Model):
    GRADE_CHOICES = [
        ('fifa', 'FIFA'),
        ('national', 'National'),
        ('regional', 'Regional'),
        ('county', 'County'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referee')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    id_number = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    grade = models.CharField(max_length=20, choices=GRADE_CHOICES)
    license_number = models.CharField(max_length=50, unique=True)
    photo = models.ImageField(upload_to='referee_photos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.grade}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class MatchReport(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    match = models.OneToOneField('matches.Match', on_delete=models.CASCADE, related_name='report')
    referee = models.ForeignKey(Referee, on_delete=models.CASCADE, related_name='reports')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Match details
    weather_conditions = models.CharField(max_length=100, blank=True)
    pitch_conditions = models.CharField(max_length=100, blank=True)
    attendance = models.IntegerField(null=True, blank=True)
    
    # Incidents
    major_incidents = models.TextField(blank=True)
    referee_comments = models.TextField(blank=True)
    
    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_reports')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Report for {self.match}"
    
    def submit_report(self):
        self.status = 'submitted'
        self.submitted_at = timezone.now()
        self.save()