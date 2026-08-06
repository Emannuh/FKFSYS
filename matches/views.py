# matches/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Match, LeagueTable, Goal, Card
from teams.models import Zone, Team, Player
from referees.models import MatchReport
from fkf_league.permissions import is_league_admin
from fkf_league.constants import MatchStatus

# ── Permission wrappers ────────────────────────────────────────────────────
def league_admin_required(user):
    return is_league_admin(user)

def league_manager_required(user):
    return user.groups.filter(name='League Manager').exists() or user.is_superuser


# ── Public views ───────────────────────────────────────────────────────────

def match_results(request):
    """List all completed match results."""
    matches = (
        Match.objects
        .filter(status=MatchStatus.COMPLETED)
        .select_related('home_team', 'away_team', 'zone')
        .order_by('-match_date')
    )
    return render(request, 'matches/match_results.html', {'matches': matches})


def league_tables(request):
    """League standings — select_related prevents N+1 on team names."""
    zones = Zone.objects.all()

    tables = {
        zone: (
            LeagueTable.objects
            .filter(zone=zone)
            .select_related('team', 'team__zone')
            .order_by('-points', '-goal_difference', '-goals_for')
        )[:20]
        for zone in zones
    }

    top_scorers = (
        Player.objects
        .filter(goals_scored__gt=0)
        .select_related('team')
        .order_by('-goals_scored')[:10]
    )
    goalkeepers = (
        Player.objects
        .filter(position='GK', matches_played__gt=0)
        .select_related('team')
        .order_by('-clean_sheets', '-matches_played')[:10]
    )

    return render(request, 'matches/league_tables.html', {
        'tables':      tables,
        'top_scorers': top_scorers,
        'goalkeepers': goalkeepers,
        'zones':       zones,
    })


def fixtures(request):
    """Fixtures with filtering.  All three status counts come from one aggregate."""
    zone_filter   = request.GET.get('zone',   'all')
    round_filter  = request.GET.get('round',  'all')
    status_filter = request.GET.get('status', 'upcoming')
    date_filter   = request.GET.get('date',   '')
    today         = timezone.now()

    base = Match.objects.select_related('home_team', 'away_team', 'zone')

    # ── Counts via single aggregate (no extra queries) ───────────────────
    counts = Match.objects.aggregate(
        all_count      = Count('id'),
        upcoming_count = Count('id', filter=Q(
            status__in=MatchStatus.ACTIVE_STATUSES,
            match_date__gte=today,
        )),
        completed_count = Count('id', filter=Q(status=MatchStatus.COMPLETED)),
    )

    # ── Filtering ────────────────────────────────────────────────────────
    qs = base.order_by('match_date')

    if zone_filter != 'all':
        qs = qs.filter(zone_id=zone_filter)
    if round_filter != 'all':
        qs = qs.filter(round_number=round_filter)
    if date_filter:
        try:
            qs = qs.filter(match_date__date=datetime.strptime(date_filter, '%Y-%m-%d').date())
        except ValueError:
            pass

    if status_filter == 'upcoming':
        qs = qs.filter(status__in=MatchStatus.ACTIVE_STATUSES, match_date__gte=today)
    elif status_filter == 'completed':
        qs = qs.filter(status=MatchStatus.COMPLETED)
    elif status_filter == 'today':
        qs = qs.filter(match_date__date=today.date())
    elif status_filter == 'weekend':
        days_to_sat = (5 - today.weekday()) % 7
        sat = today.date() + timedelta(days=days_to_sat)
        qs = qs.filter(match_date__date__in=[sat, sat + timedelta(days=1)])

    rounds = Match.objects.values_list('round_number', flat=True).distinct().order_by('round_number')

    return render(request, 'matches/fixtures.html', {
        'upcoming_matches':  qs.filter(status__in=MatchStatus.ACTIVE_STATUSES),
        'completed_matches': qs.filter(status=MatchStatus.COMPLETED),
        'zones':             Zone.objects.all(),
        'rounds':            rounds,
        'selected_zone':     zone_filter,
        'selected_round':    round_filter,
        'selected_status':   status_filter,
        'selected_date':     date_filter,
        'all_count':         counts['all_count'],
        'upcoming_count':    counts['upcoming_count'],
        'completed_count':   counts['completed_count'],
        'today':             today.date(),
    })


def match_details(request, match_id):
    """Match detail page — goals, cards, report."""
    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team', 'zone', 'referee'),
        id=match_id,
    )
    try:
        report = MatchReport.objects.get(match=match)
    except MatchReport.DoesNotExist:
        report = None

    return render(request, 'matches/match_details.html', {
        'match':  match,
        'report': report,
        'goals':  Goal.objects.filter(match=match).select_related('scorer', 'team').order_by('minute'),
        'cards':  Card.objects.filter(match=match).select_related('player', 'team').order_by('minute'),
    })


def top_scorers(request):
    """Top scorers list with per-zone breakdown — single queryset, no N+1."""
    zones   = Zone.objects.all()
    scorers = (
        Player.objects
        .filter(goals_scored__gt=0)
        .select_related('team', 'team__zone')
        .order_by('-goals_scored')
    )
    scorers_by_zone = {zone: scorers.filter(team__zone=zone)[:20] for zone in zones}

    return render(request, 'matches/top_scorers.html', {
        'top_scorers':      scorers,
        'scorers_by_zone':  scorers_by_zone,
        'zones':            zones,
    })


def team_fixtures(request, team_id):
    """All fixtures for a specific team."""
    team    = get_object_or_404(Team, id=team_id)
    matches = (
        Match.objects
        .filter(Q(home_team=team) | Q(away_team=team))
        .select_related('home_team', 'away_team', 'zone')
        .order_by('match_date')
    )
    return render(request, 'matches/team_fixtures.html', {
        'team':              team,
        'upcoming_matches':  matches.filter(status=MatchStatus.SCHEDULED),
        'completed_matches': matches.filter(status=MatchStatus.COMPLETED),
    })


def zone_fixtures(request, zone_id):
    """All fixtures for a specific zone."""
    zone    = get_object_or_404(Zone, id=zone_id)
    matches = (
        Match.objects
        .filter(zone=zone)
        .select_related('home_team', 'away_team')
        .order_by('match_date')
    )
    return render(request, 'matches/zone_fixtures.html', {
        'zone':              zone,
        'upcoming_matches':  matches.filter(status=MatchStatus.SCHEDULED),
        'completed_matches': matches.filter(status=MatchStatus.COMPLETED),
    })


# ── Admin / staff views ────────────────────────────────────────────────────

@login_required
@user_passes_test(league_admin_required)
def admin_edit_match_result(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        try:
            match.home_score = int(request.POST.get('home_score', match.home_score))
            match.away_score = int(request.POST.get('away_score', match.away_score))
            match.status     = MatchStatus.COMPLETED
            match.save()
            messages.success(request, '✅ Match result updated.')
            return redirect('matches:match_results')
        except Exception as exc:
            messages.error(request, f'❌ Error: {exc}')
    return render(request, 'admin_dashboard/edit_match_result.html', {'match': match})


@login_required
@user_passes_test(league_admin_required)
def admin_edit_league_table(request, table_id):
    table = get_object_or_404(LeagueTable, id=table_id)
    if request.method == 'POST':
        try:
            table.matches_played  = int(request.POST.get('matches_played',  table.matches_played))
            table.wins            = int(request.POST.get('wins',            table.wins))
            table.draws           = int(request.POST.get('draws',           table.draws))
            table.losses          = int(request.POST.get('losses',          table.losses))
            table.goals_for       = int(request.POST.get('goals_for',       table.goals_for))
            table.goals_against   = int(request.POST.get('goals_against',   table.goals_against))
            # goal_difference and points auto-calculated in LeagueTable.save()
            table.save()
            messages.success(request, '✅ League table updated.')
            return redirect('matches:league_tables')
        except Exception as exc:
            messages.error(request, f'❌ Error: {exc}')
    return render(request, 'admin_dashboard/edit_league_table.html', {'table': table})


@login_required
@user_passes_test(league_manager_required)
def league_manager_reschedule(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if not is_league_admin(request.user):
        messages.error(request, 'Only league admins can reschedule fixtures.')
        return redirect('matches:match_details', match_id=match_id)
    if request.method == 'POST':
        try:
            match.match_date   = timezone.make_aware(datetime.strptime(request.POST['new_date'], '%Y-%m-%d'))
            match.kickoff_time = request.POST.get('new_kickoff_time')
            match.status       = MatchStatus.SCHEDULED
            match.save()
            messages.success(request, '✅ Match rescheduled.')
            return redirect('matches:match_details', match_id=match_id)
        except Exception as exc:
            messages.error(request, f'❌ Error: {exc}')
    return render(request, 'admin_dashboard/league_manager_reschedule.html', {'match': match})


@login_required
@user_passes_test(league_manager_required)
@require_POST
def start_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if match.is_live:
        messages.info(request, 'Match is already live.')
    else:
        match.status     = MatchStatus.LIVE
        match.start_time = timezone.now()
        match.save()
        messages.success(request, 'Match started and is now LIVE.')
    return redirect('matches:match_details', match_id=match.id)


@login_required
def view_match_officials(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    return render(request, 'matches/view_match_officials.html', {'match': match})
