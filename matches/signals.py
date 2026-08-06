# matches/signals.py
from django.db.models.signals import post_save
from django.db.models import Q
from django.dispatch import receiver

from matches.models import Match, LeagueTable
from teams.models import Team
from matches.utils.fixture_generator import generate_fixtures_for_zone


# ── League table form (last 5 results) ──────────────────────────────────────

@receiver(post_save, sender=Match)
def update_league_table_form(sender, instance, **kwargs):
    """Keep each team's form string (last 5 results: W/D/L) up to date."""
    if instance.status != 'completed':
        return

    for team in (instance.home_team, instance.away_team):
        recent = (
            Match.objects.filter(
                Q(home_team=team) | Q(away_team=team),
                status='completed',
            )
            .order_by('-match_date')[:5]
        )
        # Use result_for() — defined on Match model — instead of duplicating logic here
        form = ''.join(
            r for m in recent
            if (r := m.result_for(team)) is not None
        )
        try:
            lt = LeagueTable.objects.get(team=team, zone=instance.zone)
            lt.form = form
            lt.save(update_fields=['form', 'last_updated'])
        except LeagueTable.DoesNotExist:
            pass


# ── Auto-generate fixtures when a zone reaches minimum team count ────────────

@receiver(post_save, sender=Team)
def auto_generate_fixtures_on_team_approval(sender, instance, created, **kwargs):
    """
    Automatically generate fixtures when:
    1. A team is approved AND assigned to a zone
    2. The zone reaches the minimum required team count
    3. Fixtures haven't been generated yet
    """
    if instance.status != 'approved' or not instance.zone:
        return

    zone = instance.zone
    if zone.fixtures_generated:
        return

    MINIMUM_TEAMS_REQUIRED = 4
    count = Team.objects.filter(zone=zone, status='approved').count()

    if count >= MINIMUM_TEAMS_REQUIRED:
        success, message = generate_fixtures_for_zone(zone.id)
        import logging as _log
        _log.getLogger(__name__).info("Auto-generated fixtures for zone %s: %s", zone.name, message)


# ── Ensure LeagueTable entry exists for approved teams ───────────────────────

@receiver(post_save, sender=Team)
def ensure_league_table_for_team(sender, instance, created, **kwargs):
    """
    Create a LeagueTable row when a team is approved and placed in a zone.
    NOTE: We deliberately do NOT delete rows when a team's zone is removed —
          that would destroy historical data. Archiving should be handled explicitly.
    """
    if instance.status == 'approved' and instance.zone:
        LeagueTable.objects.get_or_create(team=instance, zone=instance.zone)
