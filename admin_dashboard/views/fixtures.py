"""Fixture generation and the reschedule list (staff only)."""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from fkf_league.constants import MatchStatus, TeamStatus
from matches.models import Match
from matches.utils.fixture_generator import generate_fixtures_for_zone
from teams.models import Zone

from ..activity_logger import Action, log_activity
from .common import staff_required


class _GenerationFailed(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _generate(request, zone: Zone, regenerate: bool) -> None:
    approved_teams = zone.team_set.filter(status=TeamStatus.APPROVED).count()
    if approved_teams < 2:
        messages.error(request, f"Cannot generate fixtures for {zone.name}. At least 2 approved teams "
                                f"are required (currently has {approved_teams}).")
        return

    existing = Match.objects.filter(zone=zone)
    if regenerate and zone.fixtures_generated:
        played = existing.filter(status__in=[MatchStatus.COMPLETED, MatchStatus.ONGOING]).count()
        if played:
            messages.error(request, f"Cannot regenerate fixtures for {zone.name}. {played} match(es) have "
                                    f"already been played or are ongoing.")
            log_activity(request.user, Action.FIXTURE_REGENERATE,
                         f"Refused fixture regeneration for {zone.name}: {played} match(es) played",
                         obj=zone, request=request, extra_data={'played_matches': played, 'success': False})
            return

    deleted = 0
    try:
        # Delete + regenerate atomically: a failed generation keeps the old fixtures.
        with transaction.atomic():
            if regenerate and zone.fixtures_generated:
                deleted = existing.count()
                existing.delete()
                zone.fixtures_generated = False
                zone.fixture_generation_date = None
                zone.save(update_fields=['fixtures_generated', 'fixture_generation_date'])
            success, message = generate_fixtures_for_zone(zone.id)
            if not success:
                raise _GenerationFailed(message)
    except _GenerationFailed as exc:
        messages.error(request, f"Failed to generate fixtures: {exc.message}")
        log_activity(request.user, Action.FIXTURE_GENERATE, f"Failed to generate fixtures for {zone.name}",
                     obj=zone, request=request, extra_data={'success': False, 'error': str(exc.message)[:300]})
        return

    match_count = Match.objects.filter(zone=zone).count()
    verb = 'Regenerated' if regenerate else 'Generated'
    messages.success(request, f"{verb} {match_count} fixtures for {zone.name}. {message}")
    log_activity(request.user, Action.FIXTURE_REGENERATE if regenerate else Action.FIXTURE_GENERATE,
                 f"{verb} {match_count} fixtures for {zone.name}", obj=zone, request=request,
                 extra_data={'match_count': match_count, 'deleted_count': deleted,
                             'approved_teams': approved_teams, 'success': True})


@staff_required
def generate_fixtures_admin(request):
    if request.method == 'POST':
        zone = get_object_or_404(Zone, id=request.POST.get('zone_id'))
        regenerate = request.POST.get('regenerate') == 'true'
        if zone.fixtures_generated and not regenerate:
            messages.warning(request, f"Fixtures for {zone.name} have already been generated. Use the "
                                      f"Regenerate button if you want to create new fixtures.")
        else:
            _generate(request, zone, regenerate)
        return redirect('admin_dashboard:generate_fixtures_admin')

    zones = Zone.objects.order_by('name')
    counts = zones.aggregate(
        total=Count('id'),
        with_fixtures=Count('id', filter=Q(fixtures_generated=True)),
    )
    return render(request, 'admin/generate_fixtures.html', {
        'zones': zones,
        'total_zones': counts['total'],
        'zones_with_fixtures': counts['with_fixtures'],
        'zones_pending': counts['total'] - counts['with_fixtures'],
    })


@staff_required
def reschedule_fixtures_admin(request):
    matches = (
        Match.objects.filter(status__in=[MatchStatus.SCHEDULED, MatchStatus.POSTPONED])
        .select_related('home_team', 'away_team', 'zone')
        .order_by('match_date')
    )
    return render(request, 'admin_dashboard/reschedule_fixtures.html', {'matches': matches})
