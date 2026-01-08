# matches/signals.py - CREATE THIS NEW FILE
from django.db.models.signals import post_save
from django.dispatch import receiver
from teams.models import Team, Zone
from matches.utils.fixture_generator import generate_fixtures_for_zone

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