import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from teams.models import Team

from . import services
from .models import LeagueTable, Match
from .utils.fixture_generator import MINIMUM_TEAMS_FOR_AUTO_FIXTURES, generate_fixtures_for_zone

logger = logging.getLogger(__name__)


# ── League table: derived from completed matches ────────────────────────────

@receiver(pre_save, sender=Match)
def remember_previous_match_state(sender, instance, raw=False, **kwargs):
    """Remember the stored zone/teams/status so a change can refresh the old rows too."""
    instance._standings_before = None
    if raw or not instance.pk:
        return
    instance._standings_before = (
        Match.objects.filter(pk=instance.pk)
        .values_list('zone_id', 'home_team_id', 'away_team_id', 'status')
        .first()
    )


@receiver(post_save, sender=Match)
def update_standings_on_match_save(sender, instance, raw=False, **kwargs):
    if raw:
        return
    before = getattr(instance, '_standings_before', None)
    was_completed = bool(before and before[3] == Match.Status.COMPLETED)
    if not (was_completed or instance.status == Match.Status.COMPLETED):
        return
    services.recalculate_for_match(instance)
    if before and tuple(before[:3]) != (instance.zone_id, instance.home_team_id, instance.away_team_id):
        zone_id, home_id, away_id = before[:3]
        for team_id in (home_id, away_id):
            services.recalculate_standing(team_id, zone_id)


@receiver(post_delete, sender=Match)
def update_standings_on_match_delete(sender, instance, **kwargs):
    if instance.status == Match.Status.COMPLETED:
        services.recalculate_for_match(instance)


# ── Teams: league-table row + automatic fixtures ────────────────────────────

@receiver(post_save, sender=Team)
def ensure_league_table_for_team(sender, instance, raw=False, **kwargs):
    """
    Create a LeagueTable row when a team is approved and placed in a zone.
    Rows are never deleted here (that would destroy history).
    """
    if not raw and instance.status == 'approved' and instance.zone_id:
        LeagueTable.objects.get_or_create(team=instance, zone_id=instance.zone_id)


@receiver(post_save, sender=Team)
def auto_generate_fixtures_on_team_approval(sender, instance, raw=False, **kwargs):
    """Generate a zone's fixtures once it first reaches the minimum number of approved teams."""
    if raw or instance.status != 'approved' or not instance.zone_id:
        return
    zone = instance.zone
    if zone.fixtures_generated:
        return
    if Team.objects.filter(zone=zone, status='approved').count() < MINIMUM_TEAMS_FOR_AUTO_FIXTURES:
        return

    def _generate():
        success, _message = generate_fixtures_for_zone(zone.pk)
        logger.info("Auto fixture generation for zone %s: success=%s", zone.pk, success)

    # After commit, so a bulk approval in one transaction generates once with all teams.
    transaction.on_commit(_generate)
