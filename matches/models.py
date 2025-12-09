from django.db import models
from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from django.utils import timezone

from teams.models import Team, Player


class Match(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('postponed', 'Postponed'),
        ('cancelled', 'Cancelled'),
    ]
    
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')
    zone = models.ForeignKey('teams.Zone', on_delete=models.CASCADE)
    match_date = models.DateTimeField()
    venue = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Scores
    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    
    # Match officials
    referee = models.ForeignKey('referees.Referee', on_delete=models.SET_NULL, null=True, blank=True)
    assistant_referee_1 = models.ForeignKey('referees.Referee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assistant_referee_1_matches')
    assistant_referee_2 = models.ForeignKey('referees.Referee', on_delete=models.SET_NULL, null=True, blank=True, related_name='assistant_referee_2_matches')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['match_date']
        verbose_name_plural = 'matches'
    
    def __str__(self):
        return f"{self.home_team} vs {self.away_team} - {self.match_date.strftime('%Y-%m-%d')}"
    
    @property
    def winner(self):
        if self.home_score > self.away_score:
            return self.home_team
        elif self.away_score > self.home_score:
            return self.away_team
        return None


class Goal(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='goals')
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
    
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='cards')
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
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-points', '-goal_difference', '-goals_for']
        unique_together = ['team', 'zone']
    
    def __str__(self):
        return f"{self.team.team_name} - {self.points} points"
    
    def calculate_points(self):
        self.points = (self.wins * 3) + (self.draws * 1)
    
    def update_stats(self):
        # This will be updated when matches are recorded
        pass


# ----------------------------
# Suspension model (new)
# ----------------------------
class Suspension(models.Model):
    REASON_CHOICES = [
        ('red_card', 'Direct Red Card'),
        ('double_yellow', 'Two Yellow Cards in One Match'),
        ('accumulated_yellow', '6 Accumulated Yellow Cards'),
        ('violent_conduct', 'Violent Conduct'),
        ('other', 'Other'),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='suspensions')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, null=True, blank=True)
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
        # optional rule: active suspensions generally should have at least 1 match_missed
        if self.is_active and self.matches_missed == 0:
            raise ValidationError("Active suspensions should have a positive matches_missed value.")

    @property
    def matches_remaining(self):
        remaining = self.matches_missed - self.matches_served
        return remaining if remaining > 0 else 0

    def save(self, *args, **kwargs):
        # validate before saving
        self.full_clean()

        super().save(*args, **kwargs)

        # synchronize player suspension flags in the database directly (avoid extra racey read/write)
        if self.is_active and self.matches_remaining > 0:
            # set player as suspended; adjust field names if your Player model differs
            Player.objects.filter(pk=self.player.pk).update(
                is_suspended=True,
                suspension_end=self.end_date if self.end_date else None,
            )
        else:
            # clear player suspension only if no other active suspensions exist
            other_active = Suspension.objects.filter(player=self.player, is_active=True).exclude(pk=self.pk).exists()
            if not other_active:
                Player.objects.filter(pk=self.player.pk).update(
                    is_suspended=False,
                    suspension_end=None,
                )

    def serve_match(self):
        """Mark one match as served in a concurrency-safe way and close suspension when done.
        Returns the new matches_served value.
        """
        if not self.is_active:
            return self.matches_served

        with transaction.atomic():
            s = Suspension.objects.select_for_update().get(pk=self.pk)
            Suspension.objects.filter(pk=self.pk).update(matches_served=F('matches_served') + 1)
            s.refresh_from_db()

            if s.matches_served >= s.matches_missed:
                s.is_active = False
                s.end_date = s.end_date or timezone.now().date()
                s.save()

                other_active = Suspension.objects.filter(player=s.player, is_active=True).exclude(pk=s.pk).exists()
                if not other_active:
                    Player.objects.filter(pk=s.player.pk).update(
                        is_suspended=False,
                        suspension_end=None,
                    )

            return s.matches_served

# NOTE: If your Player model uses different field names for suspension state (e.g. `suspended_until`),
# adjust the `Player.objects.filter(...).update(...)` calls above accordingly.
