from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class LeagueStanding(models.Model):
    zone = models.ForeignKey('teams.Zone', on_delete=models.CASCADE)
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    
    position = models.IntegerField(default=0)
    matches_played = models.IntegerField(default=0)
    matches_won = models.IntegerField(default=0)
    matches_drawn = models.IntegerField(default=0)
    matches_lost = models.IntegerField(default=0)
    goals_for = models.IntegerField(default=0)
    goals_against = models.IntegerField(default=0)
    goal_difference = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    
    yellow_cards = models.IntegerField(default=0)
    red_cards = models.IntegerField(default=0)
    fair_play_points = models.IntegerField(default=100)
    
    form = models.CharField(max_length=20, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    season = models.CharField(max_length=20, default=timezone.now().year)
    
    class Meta:
        ordering = ['zone', '-points', '-goal_difference', '-goals_for']
        unique_together = ['zone', 'team', 'season']
    
    def __str__(self):
        return f"{self.team} - {self.zone} - {self.points} points"
    
    def calculate_standings(self):
        self.matches_played = self.team.matches_played
        self.matches_won = self.team.matches_won
        self.matches_drawn = self.team.matches_drawn
        self.matches_lost = self.team.matches_lost
        self.goals_for = self.team.goals_for
        self.goals_against = self.team.goals_against
        self.goal_difference = self.team.goal_difference
        self.points = self.team.points
        self.yellow_cards = self.team.total_yellow_cards
        self.red_cards = self.team.total_red_cards
        self.fair_play_points = self.team.fair_play_points
        self.form = self.team.current_form
        self.save()

class PlayerStatistic(models.Model):
    player = models.ForeignKey('teams.Player', on_delete=models.CASCADE)
    season = models.CharField(max_length=20, default=timezone.now().year)
    
    appearances = models.IntegerField(default=0)
    starts = models.IntegerField(default=0)
    minutes_played = models.IntegerField(default=0)
    
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    shots = models.IntegerField(default=0)
    shots_on_target = models.IntegerField(default=0)
    
    passes = models.IntegerField(default=0)
    passes_completed = models.IntegerField(default=0)
    
    tackles = models.IntegerField(default=0)
    interceptions = models.IntegerField(default=0)
    clearances = models.IntegerField(default=0)
    
    saves = models.IntegerField(default=0)
    clean_sheets = models.IntegerField(default=0)
    penalties_saved = models.IntegerField(default=0)
    goals_conceded = models.IntegerField(default=0)
    
    yellow_cards = models.IntegerField(default=0)
    red_cards = models.IntegerField(default=0)
    
    man_of_match = models.IntegerField(default=0)
    
    average_rating = models.FloatField(default=0.0)
    
    class Meta:
        ordering = ['-goals', '-assists', '-average_rating']
        unique_together = ['player', 'season']
    
    def __str__(self):
        return f"{self.player} - {self.season}"
    
    @property
    def pass_accuracy(self):
        if self.passes > 0:
            return round((self.passes_completed / self.passes) * 100, 1)
        return 0
    
    @property
    def goals_per_match(self):
        if self.appearances > 0:
            return round(self.goals / self.appearances, 2)
        return 0

class CleanSheetStanding(models.Model):
    goalkeeper = models.ForeignKey('teams.Player', on_delete=models.CASCADE)
    clean_sheets = models.IntegerField(default=0)
    matches_played = models.IntegerField(default=0)
    goals_conceded = models.IntegerField(default=0)
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    season = models.CharField(max_length=20, default=timezone.now().year)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-clean_sheets', 'goals_conceded']
        unique_together = ['goalkeeper', 'season']
    
    def __str__(self):
        return f"{self.goalkeeper} - {self.clean_sheets} clean sheets"
    
    @property
    def clean_sheet_percentage(self):
        if self.matches_played > 0:
            return round((self.clean_sheets / self.matches_played) * 100, 1)
        return 0

class FairPlayStanding(models.Model):
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    fair_play_points = models.IntegerField(default=100)
    yellow_cards = models.IntegerField(default=0)
    red_cards = models.IntegerField(default=0)
    zone = models.ForeignKey('teams.Zone', on_delete=models.CASCADE)
    season = models.CharField(max_length=20, default=timezone.now().year)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-fair_play_points']
        unique_together = ['team', 'season']
    
    def __str__(self):
        return f"{self.team} - {self.fair_play_points} points"
    def calculate_fair_play(self):
        self.yellow_cards = self.team.total_yellow_cards
        self.red_cards = self.team.total_red_cards
        self.fair_play_points = 100 - (self.yellow_cards + (self.red_cards * 3))
        self.save()     
        