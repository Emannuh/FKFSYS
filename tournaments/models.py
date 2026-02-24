from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

from teams.models import Team, Player, Zone


# ---------------------------------------------------------------------------
#  TOURNAMENT
# ---------------------------------------------------------------------------
class Tournament(models.Model):
    FORMAT_CHOICES = [
        ('knockout', 'Knockout'),
        ('group_knockout', 'Group Stage + Knockout'),
        ('round_robin', 'Round Robin'),
        ('swiss', 'Swiss System'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('registration', 'Registration Open'),
        ('registration_closed', 'Registration Closed'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Core info
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    banner = models.ImageField(upload_to='tournament_banners/', blank=True, null=True)
    logo = models.ImageField(upload_to='tournament_logos/', blank=True, null=True)

    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    registration_deadline = models.DateTimeField(
        help_text="Teams can register until this date/time."
    )

    # Structure
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='knockout')
    max_teams = models.PositiveIntegerField(default=16)
    min_squad_size = models.PositiveIntegerField(default=15)
    max_squad_size = models.PositiveIntegerField(default=25)
    group_count = models.PositiveIntegerField(
        default=4,
        help_text="Number of groups (only for Group Stage + Knockout format)."
    )

    # Allow external (non-league) teams
    allow_external_teams = models.BooleanField(
        default=True,
        help_text="Allow teams not in the FKF County League to register."
    )

    # Geography
    zone = models.ForeignKey(
        Zone, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Leave blank for county-wide tournaments."
    )
    venue = models.CharField(max_length=200, blank=True)

    # Status / workflow
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='draft')

    # Rules (rich-text friendly; just stored as text for now)
    rules = models.TextField(blank=True, help_text="Tournament rules & regulations.")
    prize_info = models.TextField(blank=True, help_text="Prize breakdown.")
    entry_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Ownership
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='created_tournaments',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.name)
            slug = base
            n = 1
            while Tournament.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

    @property
    def is_registration_open(self):
        return (
            self.status == 'registration'
            and timezone.now() <= self.registration_deadline
        )

    @property
    def registered_teams_count(self):
        return self.registrations.filter(status='approved').count()


# ---------------------------------------------------------------------------
#  EXTERNAL TEAM  (teams NOT in the FKF County League)
# ---------------------------------------------------------------------------
class ExternalTeam(models.Model):
    """For teams that are not registered in the league system."""
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name='external_teams'
    )
    team_name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='tournament_external_logos/', blank=True, null=True)
    location = models.CharField(max_length=200, blank=True)
    home_ground = models.CharField(max_length=200, blank=True)

    # Contact
    contact_person = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)

    # Kit colours (simplified)
    home_jersey_color = models.CharField(max_length=50, blank=True, default='#dc3545')
    away_jersey_color = models.CharField(max_length=50, blank=True, default='#ffffff')

    # Optional user account created for external team manager
    manager_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='external_teams_managed',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tournament', 'team_name')
        ordering = ['team_name']

    def __str__(self):
        return self.team_name


# ---------------------------------------------------------------------------
#  EXTERNAL PLAYER  (players NOT in the FKF County League)
# ---------------------------------------------------------------------------
class ExternalPlayer(models.Model):
    POSITION_CHOICES = [
        ('GK', 'Goalkeeper'),
        ('DF', 'Defender'),
        ('MF', 'Midfielder'),
        ('FW', 'Forward'),
    ]

    external_team = models.ForeignKey(
        ExternalTeam, on_delete=models.CASCADE, related_name='players'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    id_number = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='tournament_external_players/', blank=True, null=True)
    position = models.CharField(max_length=2, choices=POSITION_CHOICES)
    jersey_number = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('external_team', 'jersey_number')
        ordering = ['jersey_number']

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name


# ---------------------------------------------------------------------------
#  TOURNAMENT TEAM REGISTRATION  (supports LEAGUE teams + EXTERNAL teams)
# ---------------------------------------------------------------------------
class TournamentTeamRegistration(models.Model):
    REG_STATUS = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    TEAM_TYPE_CHOICES = [
        ('league', 'FKF League Team'),
        ('external', 'External Team'),
    ]

    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name='registrations'
    )

    # -- One of these will be set, the other null --
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE,
        related_name='tournament_registrations',
        null=True, blank=True,
        help_text="For teams already in the FKF County League."
    )
    external_team = models.ForeignKey(
        ExternalTeam, on_delete=models.CASCADE,
        related_name='tournament_registrations',
        null=True, blank=True,
        help_text="For teams NOT in the FKF County League."
    )
    team_type = models.CharField(
        max_length=10, choices=TEAM_TYPE_CHOICES, default='league'
    )

    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    status = models.CharField(max_length=15, choices=REG_STATUS, default='pending')
    rejection_reason = models.TextField(blank=True)
    payment_confirmed = models.BooleanField(default=False)
    seed = models.PositiveIntegerField(null=True, blank=True, help_text="Seeding number.")

    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['seed', 'registered_at']

    def clean(self):
        if self.team_type == 'league' and not self.team:
            raise ValidationError("League team registration requires a league team.")
        if self.team_type == 'external' and not self.external_team:
            raise ValidationError("External team registration requires an external team.")

    @property
    def display_name(self):
        """Returns the team name regardless of type."""
        if self.team_type == 'league' and self.team:
            return self.team.team_name
        elif self.team_type == 'external' and self.external_team:
            return self.external_team.team_name
        return "Unknown Team"

    def __str__(self):
        return f"{self.display_name} → {self.tournament}"


# ---------------------------------------------------------------------------
#  TOURNAMENT PLAYER REGISTRATION  (squad per tournament)
#  Supports BOTH league players and external players
# ---------------------------------------------------------------------------
class TournamentPlayerRegistration(models.Model):
    STATUS_CHOICES = [
        ('registered', 'Registered'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name='player_registrations'
    )
    team_registration = models.ForeignKey(
        TournamentTeamRegistration, on_delete=models.CASCADE,
        related_name='player_registrations'
    )

    # -- One of these will be set --
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE,
        related_name='tournament_registrations',
        null=True, blank=True,
        help_text="League player (if team is from the league)."
    )
    external_player = models.ForeignKey(
        ExternalPlayer, on_delete=models.CASCADE,
        related_name='tournament_registrations',
        null=True, blank=True,
        help_text="External player (if team is external)."
    )

    jersey_number = models.PositiveIntegerField(
        help_text="Jersey number for this tournament."
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='registered')

    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['jersey_number']

    @property
    def player_name(self):
        if self.player:
            return self.player.full_name
        elif self.external_player:
            return self.external_player.full_name
        return "Unknown Player"

    def __str__(self):
        return f"{self.player_name} (#{self.jersey_number}) – {self.tournament}"


# ---------------------------------------------------------------------------
#  GROUP  (for group-stage formats)
# ---------------------------------------------------------------------------
class TournamentGroup(models.Model):
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name='groups'
    )
    name = models.CharField(max_length=50, help_text="e.g. Group A")
    teams = models.ManyToManyField(
        TournamentTeamRegistration, blank=True, related_name='groups'
    )

    class Meta:
        unique_together = ('tournament', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.tournament} – {self.name}"


# ---------------------------------------------------------------------------
#  GROUP STANDING  (precomputed for speed)
# ---------------------------------------------------------------------------
class TournamentGroupStanding(models.Model):
    group = models.ForeignKey(
        TournamentGroup, on_delete=models.CASCADE, related_name='standings'
    )
    team_registration = models.ForeignKey(
        TournamentTeamRegistration, on_delete=models.CASCADE
    )
    played = models.PositiveIntegerField(default=0)
    won = models.PositiveIntegerField(default=0)
    drawn = models.PositiveIntegerField(default=0)
    lost = models.PositiveIntegerField(default=0)
    goals_for = models.PositiveIntegerField(default=0)
    goals_against = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('group', 'team_registration')
        ordering = ['-won', '-goals_for', 'goals_against']

    @property
    def points(self):
        return self.won * 3 + self.drawn

    @property
    def goal_difference(self):
        return self.goals_for - self.goals_against

    def __str__(self):
        return f"{self.team_registration.team} – {self.group}"


# ---------------------------------------------------------------------------
#  TOURNAMENT MATCH
# ---------------------------------------------------------------------------
class TournamentMatch(models.Model):
    STAGE_CHOICES = [
        ('group', 'Group Stage'),
        ('round_of_32', 'Round of 32'),
        ('round_of_16', 'Round of 16'),
        ('quarter_final', 'Quarter Final'),
        ('semi_final', 'Semi Final'),
        ('third_place', 'Third Place Playoff'),
        ('final', 'Final'),
    ]

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('completed', 'Completed'),
        ('postponed', 'Postponed'),
        ('cancelled', 'Cancelled'),
    ]

    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name='matches'
    )
    group = models.ForeignKey(
        TournamentGroup, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='matches'
    )
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='group')
    match_number = models.PositiveIntegerField(
        help_text="Sequence number within the stage."
    )

    home_team = models.ForeignKey(
        TournamentTeamRegistration, on_delete=models.CASCADE,
        related_name='home_tournament_matches', null=True, blank=True,
    )
    away_team = models.ForeignKey(
        TournamentTeamRegistration, on_delete=models.CASCADE,
        related_name='away_tournament_matches', null=True, blank=True,
    )

    match_date = models.DateTimeField()
    kickoff_time = models.CharField(max_length=5, blank=True, null=True)
    venue = models.CharField(max_length=200, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    start_time = models.DateTimeField(null=True, blank=True)

    home_score = models.PositiveIntegerField(default=0)
    away_score = models.PositiveIntegerField(default=0)

    # Penalties (knockout only)
    home_penalties = models.PositiveIntegerField(null=True, blank=True)
    away_penalties = models.PositiveIntegerField(null=True, blank=True)

    # Officials (reuse referee model)
    referee = models.ForeignKey(
        'referees.Referee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tournament_matches',
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['match_date', 'match_number']
        unique_together = ('tournament', 'stage', 'match_number')

    def __str__(self):
        home = self.home_team.display_name if self.home_team else 'TBD'
        away = self.away_team.display_name if self.away_team else 'TBD'
        return f"{home} vs {away} ({self.get_stage_display()})"

    @property
    def winner(self):
        if self.status != 'completed':
            return None
        if self.home_penalties is not None and self.away_penalties is not None:
            if self.home_penalties > self.away_penalties:
                return self.home_team
            elif self.away_penalties > self.home_penalties:
                return self.away_team
        if self.home_score > self.away_score:
            return self.home_team
        elif self.away_score > self.home_score:
            return self.away_team
        return None  # draw in group stage


# ---------------------------------------------------------------------------
#  TOURNAMENT GOAL  (supports league + external players)
# ---------------------------------------------------------------------------
class TournamentGoal(models.Model):
    match = models.ForeignKey(
        TournamentMatch, on_delete=models.CASCADE, related_name='goals'
    )
    # One of these:
    scorer = models.ForeignKey(
        Player, on_delete=models.CASCADE,
        related_name='tournament_goals', null=True, blank=True,
    )
    external_scorer = models.ForeignKey(
        ExternalPlayer, on_delete=models.CASCADE,
        related_name='tournament_goals', null=True, blank=True,
    )
    team_registration = models.ForeignKey(
        TournamentTeamRegistration, on_delete=models.CASCADE
    )
    minute = models.PositiveIntegerField()
    is_penalty = models.BooleanField(default=False)
    is_own_goal = models.BooleanField(default=False)

    class Meta:
        ordering = ['minute']

    @property
    def scorer_name(self):
        if self.scorer:
            return self.scorer.full_name
        elif self.external_scorer:
            return self.external_scorer.full_name
        return "Unknown"

    def __str__(self):
        return f"{self.scorer_name} – {self.minute}'"


# ---------------------------------------------------------------------------
#  TOURNAMENT CARD  (supports league + external players)
# ---------------------------------------------------------------------------
class TournamentCard(models.Model):
    CARD_CHOICES = [
        ('yellow', 'Yellow Card'),
        ('red', 'Red Card'),
    ]

    match = models.ForeignKey(
        TournamentMatch, on_delete=models.CASCADE, related_name='cards'
    )
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE,
        related_name='tournament_cards', null=True, blank=True,
    )
    external_player = models.ForeignKey(
        ExternalPlayer, on_delete=models.CASCADE,
        related_name='tournament_cards', null=True, blank=True,
    )
    team_registration = models.ForeignKey(
        TournamentTeamRegistration, on_delete=models.CASCADE
    )
    card_type = models.CharField(max_length=10, choices=CARD_CHOICES)
    minute = models.PositiveIntegerField()

    class Meta:
        ordering = ['minute']

    @property
    def player_name(self):
        if self.player:
            return self.player.full_name
        elif self.external_player:
            return self.external_player.full_name
        return "Unknown"

    def __str__(self):
        return f"{self.card_type.title()} – {self.player_name} ({self.minute}')"


# ---------------------------------------------------------------------------
#  TOURNAMENT MATCH OFFICIALS  (mirror of league MatchOfficials)
# ---------------------------------------------------------------------------
class TournamentMatchOfficials(models.Model):
    APPOINTMENT_STATUS = [
        ('PENDING', 'Pending Appointment'),
        ('APPOINTED', 'Appointed'),
        ('CONFIRMED', 'Confirmed'),
        ('COMPLETED', 'Match Completed'),
    ]

    match = models.OneToOneField(
        TournamentMatch, on_delete=models.CASCADE, related_name='officials'
    )

    # Required officials
    main_referee = models.ForeignKey(
        'referees.Referee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tournament_appointed_main',
    )
    assistant_1 = models.ForeignKey(
        'referees.Referee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tournament_appointed_ar1',
    )
    assistant_2 = models.ForeignKey(
        'referees.Referee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tournament_appointed_ar2',
    )

    # Optional officials
    fourth_official = models.ForeignKey(
        'referees.Referee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tournament_appointed_fourth',
    )
    match_commissioner = models.ForeignKey(
        'referees.Referee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tournament_appointed_commissioner',
    )

    status = models.CharField(max_length=20, choices=APPOINTMENT_STATUS, default='PENDING')

    appointed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    appointed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Officials for {self.match}"
