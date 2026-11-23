from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from teams.models import Player, Team


class Match(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        LIVE = 'live', 'Live'
        ONGOING = 'ongoing', 'Ongoing'
        COMPLETED = 'completed', 'Completed'
        POSTPONED = 'postponed', 'Postponed'
        CANCELLED = 'cancelled', 'Cancelled'

    # Kept for templates/views that iterate the choices.
    STATUS_CHOICES = Status.choices


    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')
    zone = models.ForeignKey('teams.Zone', on_delete=models.CASCADE)
    round_number = models.IntegerField(default=1)
    match_date = models.DateTimeField()
    kickoff_time = models.CharField(
        max_length=5, 
        blank=True, 
        null=True,
        help_text="Format: HH:MM (e.g., 15:00 for 3 PM)"
    )
    venue = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    start_time = models.DateTimeField(null=True, blank=True, help_text="Time when match went live.")
    
    # Scores
    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    
    # Match officials
    referee = models.ForeignKey('referees.Referee', on_delete=models.SET_NULL, null=True, blank=True)
    assistant_referee_1 = models.ForeignKey('referees.Referee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assistant_referee_1_matches')
    assistant_referee_2 = models.ForeignKey('referees.Referee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assistant_referee_2_matches')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __setattr__(self, name, value):
        # Defensive: callers in other apps still pass naive datetimes; store them
        # as aware (in TIME_ZONE) instead of letting Django warn and guess.
        if name == 'match_date' and isinstance(value, datetime) and timezone.is_naive(value):
            value = timezone.make_aware(value)
        super().__setattr__(name, value)

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} - {self.match_date.strftime('%Y-%m-%d')}"
    
    # ── Status helpers ──────────────────────────────────────────────────
    @property
    def is_completed(self):
        return self.status == 'completed'

    @property
    def is_live(self):
        return self.status == 'live'

    # ── Score / result helpers ───────────────────────────────────────────
    @property
    def score_display(self):
        """e.g. '2 – 1'"""
        return f"{self.home_score} \u2013 {self.away_score}"

    def result_for(self, team):
        """Return 'W', 'D', or 'L' for a given team. Returns None if not completed."""
        if not self.is_completed:
            return None
        if self.home_team_id == team.pk:
            if self.home_score > self.away_score:
                return 'W'
            if self.home_score < self.away_score:
                return 'L'
            return 'D'
        else:
            if self.away_score > self.home_score:
                return 'W'
            if self.away_score < self.home_score:
                return 'L'
            return 'D'

    # ── Kickoff datetime ─────────────────────────────────────────────────
    @property
    def kickoff_datetime(self):
        """
        Single source of truth for the match kickoff as an aware datetime.
        Eliminates the copy-pasted datetime.combine block from 3+ views.
        Falls back to match_date (already a datetime) when kickoff_time is absent.
        """
        if not self.kickoff_time:
            return self.match_date  # match_date is already a DateTimeField

        t = self.kickoff_time
        if isinstance(t, str):
            for fmt in ('%H:%M:%S', '%H:%M'):
                try:
                    t = datetime.strptime(t, fmt).time()
                    break
                except ValueError:
                    continue
            else:
                return self.match_date  # unparseable, fall back

        local_date = timezone.localtime(self.match_date).date()
        return timezone.make_aware(datetime.combine(local_date, t))


class Goal(models.Model):
    match = models.ForeignKey('Match', on_delete=models.CASCADE, related_name='goals')
    scorer = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='goals')
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    minute = models.IntegerField()
    is_penalty = models.BooleanField(default=False)
    is_own_goal = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['minute']
    
    def __str__(self):
        return f"{self.scorer.full_name} - {self.minute}'"


class Card(models.Model):
    CARD_TYPE_CHOICES = [
        ('yellow', 'Yellow Card'),
        ('red', 'Red Card'),
    ]
    
    match = models.ForeignKey('Match', on_delete=models.CASCADE, related_name='cards')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='cards')
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    card_type = models.CharField(max_length=10, choices=CARD_TYPE_CHOICES)
    minute = models.IntegerField()
    reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['minute']
    
    def __str__(self):
        return f"{self.player.full_name} - {self.get_card_type_display()} - {self.minute}'"


class LeagueTable(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='league_table')
    zone = models.ForeignKey('teams.Zone', on_delete=models.CASCADE)
    matches_played = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    goals_for = models.IntegerField(default=0)
    goals_against = models.IntegerField(default=0)
    goal_difference = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    form = models.CharField(max_length=5, default='', blank=True, help_text='Last 5 matches form (W/D/L)')
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-points', '-goal_difference', '-goals_for']
        constraints = [
            models.UniqueConstraint(fields=['team', 'zone'], name='matches_leaguetable_unique_team_zone'),
        ]
    
    def __str__(self):
        return f"{self.team.team_name} - {self.points} points"
    
    POINTS_FOR_WIN = 3
    POINTS_FOR_DRAW = 1

    def calculate_points(self):
        self.points = self.wins * self.POINTS_FOR_WIN + self.draws * self.POINTS_FOR_DRAW

    def save(self, *args, **kwargs):
        """Goal difference and points are always derived, never trusted from input."""
        self.goal_difference = self.goals_for - self.goals_against
        self.calculate_points()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'goal_difference', 'points'}
        super().save(*args, **kwargs)


class Suspension(models.Model):
    REASON_CHOICES = [
        ('red_card', 'Direct Red Card'),
        ('double_yellow', 'Two Yellow Cards in One Match'),
        ('accumulated_yellow', '6 Accumulated Yellow Cards'),
        ('violent_conduct', 'Violent Conduct'),
        ('other', 'Other'),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='suspensions')
    match = models.ForeignKey('Match', on_delete=models.CASCADE, null=True, blank=True)
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    details = models.TextField(blank=True)
    matches_missed = models.PositiveIntegerField(default=0)
    matches_served = models.PositiveIntegerField(default=0)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.player.full_name} - {self.get_reason_display()}"

    def clean(self):
        if self.matches_served > self.matches_missed:
            raise ValidationError("matches_served cannot exceed matches_missed.")
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("end_date cannot be before start_date.")
        if self.is_active and self.matches_missed == 0:
            raise ValidationError("Active suspensions should have a positive matches_missed value.")

    @property
    def matches_remaining(self):
        remaining = self.matches_missed - self.matches_served
        return remaining if remaining > 0 else 0

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

        if self.is_active and self.matches_remaining > 0:
            Player.objects.filter(pk=self.player.pk).update(
                is_suspended=True,
                suspension_end=self.end_date if self.end_date else None,
            )
        else:
            other_active = Suspension.objects.filter(player=self.player, is_active=True).exclude(pk=self.pk).exists()
            if not other_active:
                Player.objects.filter(pk=self.player.pk).update(
                    is_suspended=False,
                    suspension_end=None,
                )
