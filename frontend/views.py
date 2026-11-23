"""Public pages: home portal, about, contact, rules, and the staff-only styleguide."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q, Sum, Window
from django.db.models.functions import RowNumber
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from fkf_league.constants import MatchStatus, TeamStatus
from matches.models import LeagueTable, Match
from teams.models import Player, Team, Zone
from tournaments.models import Tournament

HOME_CACHE_KEY = 'frontend:home:v1'
HOME_CACHE_SECONDS = 60

TABLE_ROWS_PER_ZONE = 6
FIXTURES_LIMIT = 8
RESULTS_LIMIT = 6
SCORERS_LIMIT = 5
TOURNAMENTS_LIMIT = 4

LIVE_STATUSES = (MatchStatus.LIVE, MatchStatus.ONGOING)
ACTIVE_TOURNAMENT_STATUSES = ('registration', 'registration_closed', 'ongoing')


def _match_qs():
    return Match.objects.select_related('home_team', 'away_team', 'zone')


def build_home_context() -> dict[str, Any]:
    """
    Read-only, bounded queries for the home portal (one query per panel, no N+1).
    Everything is materialised into lists so the result can be cached.
    """
    now = timezone.now()

    live_matches = list(_match_qs().filter(status__in=LIVE_STATUSES).order_by('match_date')[:FIXTURES_LIMIT])

    # Next matchday = the calendar day of the next scheduled match.
    next_kickoff = (
        Match.objects.filter(status=MatchStatus.SCHEDULED, match_date__gte=now)
        .order_by('match_date').values_list('match_date', flat=True).first()
    )
    next_fixtures: list[Match] = []
    if next_kickoff:
        day_start = timezone.localtime(next_kickoff).replace(hour=0, minute=0, second=0, microsecond=0)
        next_fixtures = list(
            _match_qs()
            .filter(status=MatchStatus.SCHEDULED, match_date__gte=day_start,
                    match_date__lt=day_start + timedelta(days=1))
            .order_by('match_date', 'zone__name')[:FIXTURES_LIMIT]
        )

    latest_results = list(
        _match_qs().filter(status=MatchStatus.COMPLETED).order_by('-match_date')[:RESULTS_LIMIT]
    )

    # Top N rows per zone in one query using a window function.
    ranked_rows = (
        LeagueTable.objects.select_related('team', 'zone')
        .annotate(position=Window(
            expression=RowNumber(),
            partition_by=[F('zone_id')],
            order_by=[F('points').desc(), F('goal_difference').desc(), F('goals_for').desc(), F('team__team_name').asc()],
        ))
        .filter(position__lte=TABLE_ROWS_PER_ZONE)
        .order_by('zone__name', 'position')
    )
    zone_tables: dict[int, dict[str, Any]] = {}
    for row in ranked_rows:
        zone_tables.setdefault(row.zone_id, {'zone': row.zone, 'rows': []})['rows'].append(row)

    top_scorers = list(
        Player.objects.filter(goals_scored__gt=0)
        .select_related('team')
        .only('first_name', 'last_name', 'goals_scored', 'team__team_name', 'team__logo')
        .order_by('-goals_scored', 'last_name', 'first_name')[:SCORERS_LIMIT]
    )

    tournaments = list(
        Tournament.objects.filter(status__in=ACTIVE_TOURNAMENT_STATUSES)
        .order_by('start_date')[:TOURNAMENTS_LIMIT]
    )

    match_stats = Match.objects.aggregate(
        completed=Count('id', filter=Q(status=MatchStatus.COMPLETED)),
        goals_home=Sum('home_score', filter=Q(status=MatchStatus.COMPLETED)),
        goals_away=Sum('away_score', filter=Q(status=MatchStatus.COMPLETED)),
    )

    return {
        'live_matches': live_matches,
        'next_fixtures': next_fixtures,
        'next_matchday': timezone.localtime(next_kickoff) if next_kickoff else None,
        'latest_results': latest_results,
        'zone_tables': list(zone_tables.values()),
        'top_scorers': top_scorers,
        'tournaments': tournaments,
        'total_teams': Team.objects.filter(status=TeamStatus.APPROVED).count(),
        'completed_matches': match_stats['completed'] or 0,
        'total_goals': (match_stats['goals_home'] or 0) + (match_stats['goals_away'] or 0),
        'zone_count': Zone.objects.count(),
    }


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """Live matchday hub. Panel data is cached briefly; league_settings comes per request."""
    context = cache.get(HOME_CACHE_KEY)
    if context is None:
        context = build_home_context()
        cache.set(HOME_CACHE_KEY, context, HOME_CACHE_SECONDS)
    return render(request, 'home.html', context)


@require_GET
def about(request: HttpRequest) -> HttpResponse:
    return render(request, 'frontend/about.html')


@require_GET
def contact(request: HttpRequest) -> HttpResponse:
    return render(request, 'frontend/contact.html')


@require_GET
def rules(request: HttpRequest) -> HttpResponse:
    return render(request, 'frontend/rules.html')


@login_required
@require_GET
def styleguide(request: HttpRequest) -> HttpResponse:
    """Living reference of every design-system component (staff only)."""
    if not request.user.is_staff:
        raise PermissionDenied
    return render(request, 'frontend/styleguide.html', {
        'sample_statuses': ['pending', 'submitted', 'approved', 'locked', 'rejected'],
        'sample_match_statuses': ['scheduled', 'live', 'completed', 'postponed', 'cancelled'],
    })
