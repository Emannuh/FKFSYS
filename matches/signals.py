# matches/signals.py - CREATE THIS NEW FILE
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.db.models.signals import post_save
from django.dispatch import receiver
from matches.models import Match, LeagueTable
from teams.models import Team, Zone
from matches.utils.fixture_generator import generate_fixtures_for_zone

# --- Existing signal for fixture generation ---
# --- New signal for updating LeagueTable.form ---
@receiver(post_save, sender=Match)
def update_league_table_form(sender, instance, **kwargs):
    if instance.status != 'completed':
        return
    for team in [instance.home_team, instance.away_team]:
        # Get last 5 completed matches for this team (as home or away)
        recent_matches = Match.objects.filter(
            ((models.Q(home_team=team) | models.Q(away_team=team)) & models.Q(status='completed'))
        ).order_by('-match_date')[:5]
        form = ''
        for match in recent_matches:
            if match.home_team == team:
                if match.home_score > match.away_score:
                    form += 'W'
                elif match.home_score < match.away_score:
                    form += 'L'
                else:
                    form += 'D'
            else:
                if match.away_score > match.home_score:
                    form += 'W'
                elif match.away_score < match.home_score:
                    form += 'L'
                else:
                    form += 'D'
        # Save to LeagueTable
        try:
            league_table = LeagueTable.objects.get(team=team, zone=instance.zone)
            league_table.form = form
            league_table.save(update_fields=['form'])
        except LeagueTable.DoesNotExist:
            pass

@receiver(post_save, sender=Team)
def auto_generate_fixtures_on_team_approval(sender, instance, created, **kwargs):
    """
    AUTOMATICALLY GENERATE FIXTURES WHEN:
    1. A team is approved (status='approved')
    2. AND assigned to a zone
    3. AND zone has minimum required teams (default: 4 teams)
    4. AND fixtures haven't been generated yet
    """
    
    # Only trigger when team is approved AND has a zone
    if instance.status == 'approved' and instance.zone:
        zone = instance.zone
        
        # DON'T generate if already done
        if zone.fixtures_generated:
            return
        
        # Count how many approved teams are in this zone
        approved_teams_in_zone = Team.objects.filter(
            zone=zone,
            status='approved'
        ).count()
        
        # CONFIGURABLE: Minimum teams before auto-generation
        # Change this number if you want different minimum
        MINIMUM_TEAMS_REQUIRED = 4
        
        # If zone has enough teams, generate fixtures
        if approved_teams_in_zone >= MINIMUM_TEAMS_REQUIRED:
            # Generate fixtures automatically
            success, message = generate_fixtures_for_zone(zone.id)
            
            # Optional: Log to console (remove in production)
            print(f"🎯 AUTO-GENERATED FIXTURES: {message}")

# --- New signal: Ensure LeagueTable is created/updated for team-zone changes ---
@receiver(post_save, sender=Team)
def ensure_league_table_for_team(sender, instance, created, **kwargs):
    """
    Ensure LeagueTable entry exists and is updated when a Team is created or its zone changes.
    """
    if instance.status == 'approved' and instance.zone:
        # Create or update LeagueTable for this team and zone
        LeagueTable.objects.get_or_create(team=instance, zone=instance.zone)
    # Optionally, handle removal if team is moved out of a zone or status changes
    if instance.zone is None or instance.status != 'approved':
        LeagueTable.objects.filter(team=instance).delete()