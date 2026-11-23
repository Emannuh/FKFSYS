from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from fkf_league.constants import MatchStatus
from fkf_league.permissions import is_any_admin, is_league_admin
from referees.models import MatchOfficials, MatchReport
from teams.models import Player, Team, Zone

from .forms import LeagueTableForm, MatchResultForm
from .models import Card, Goal, LeagueTable, Match

FIXTURE_RELATED = ('home_team', 'away_team', 'zone')


# ── Public views ───────────────────────────────────────────────────────────

def match_results(request):
    """List all completed match results."""
    matches = (
        Match.objects
        .filter(status=MatchStatus.COMPLETED)
        .select_related(*FIXTURE_RELATED)
        .order_by('-match_date')
    )
    return render(request, 'matches/match_results.html', {'matches': matches})


def league_tables(request):
    zones = list(Zone.objects.order_by('pk'))
    rows_by_zone: dict[int, list] = {z.pk: [] for z in zones}
    for row in (LeagueTable.objects.select_related('team')
                .order_by('zone_id', '-points', '-goal_difference', '-goals_for', 'team__team_name')):
        bucket = rows_by_zone.setdefault(row.zone_id, [])
        if len(bucket) < 20:
            bucket.append(row)
    tables = {zone: rows_by_zone[zone.pk] for zone in zones}

    top_scorers = (
        Player.objects.filter(goals_scored__gt=0).select_related('team').order_by('-goals_scored')[:10]
    )
    goalkeepers = (
        Player.objects.filter(position='GK', matches_played__gt=0)
        .select_related('team').order_by('-clean_sheets', '-matches_played')[:10]
    )
    return render(request, 'matches/league_tables.html', {
        'tables': tables,
        'top_scorers': top_scorers,
        'goalkeepers': goalkeepers,
        'zones': zones,
        'can_edit_tables': request.user.is_authenticated and is_league_admin(request.user),
    })


def fixtures(request):
    """Fixtures with filtering. Status counts come from one aggregate."""
    zone_filter = request.GET.get('zone', 'all')
    round_filter = request.GET.get('round', 'all')
    status_filter = request.GET.get('status', 'upcoming')
    date_filter = request.GET.get('date', '')
    now = timezone.now()
    today = timezone.localdate()

    counts = Match.objects.aggregate(
        all_count=Count('id'),
        upcoming_count=Count('id', filter=Q(status__in=MatchStatus.ACTIVE_STATUSES, match_date__gte=now)),
        completed_count=Count('id', filter=Q(status=MatchStatus.COMPLETED)),
    )

    qs = Match.objects.select_related(*FIXTURE_RELATED).order_by('match_date')
    if zone_filter.isdigit():
        qs = qs.filter(zone_id=int(zone_filter))
    if round_filter.isdigit():
        qs = qs.filter(round_number=int(round_filter))
    if date_filter:
        try:
            qs = qs.filter(match_date__date=date.fromisoformat(date_filter))
        except ValueError:
            date_filter = ''

    if status_filter == 'upcoming':
        qs = qs.filter(status__in=MatchStatus.ACTIVE_STATUSES, match_date__gte=now)
    elif status_filter == 'completed':
        qs = qs.filter(status=MatchStatus.COMPLETED)
    elif status_filter == 'today':
        qs = qs.filter(match_date__date=today)
    elif status_filter == 'weekend':
        sat = today + timedelta(days=(5 - today.weekday()) % 7)
        qs = qs.filter(match_date__date__in=[sat, sat + timedelta(days=1)])

    rounds = Match.objects.values_list('round_number', flat=True).distinct().order_by('round_number')

    return render(request, 'matches/fixtures.html', {
        'upcoming_matches': qs.filter(status__in=MatchStatus.ACTIVE_STATUSES),
        'completed_matches': qs.filter(status=MatchStatus.COMPLETED),
        'zones': Zone.objects.all(),
        'rounds': rounds,
        'selected_zone': zone_filter,
        'selected_round': round_filter,
        'selected_status': status_filter,
        'selected_date': date_filter,
        'all_count': counts['all_count'],
        'upcoming_count': counts['upcoming_count'],
        'completed_count': counts['completed_count'],
        'today': today,
    })


def match_details(request, match_id):
    """Match detail page: goals, cards, report."""
    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team', 'zone', 'referee'),
        pk=match_id,
    )
    user = request.user
    return render(request, 'matches/match_details.html', {
        'match': match,
        'report': MatchReport.objects.filter(match=match).first(),
        'goals': Goal.objects.filter(match=match).select_related('scorer', 'team').order_by('minute'),
        'cards': Card.objects.filter(match=match).select_related('player', 'team').order_by('minute'),
        'can_edit_match': user.is_authenticated and user.is_staff,
        'can_edit_result': user.is_authenticated and is_league_admin(user),
        'can_view_officials': user.is_authenticated and (
            _is_officials_staff(user)
            or user.pk in (match.home_team.manager_id, match.away_team.manager_id)
            or hasattr(user, 'referee_profile')
        ),
    })


def top_scorers(request):
    """Top scorers list with per-zone breakdown."""
    zones = Zone.objects.all()
    scorers = (
        Player.objects.filter(goals_scored__gt=0)
        .select_related('team', 'team__zone')
        .order_by('-goals_scored')
    )
    return render(request, 'matches/top_scorers.html', {
        'top_scorers': scorers,
        'scorers_by_zone': {zone: scorers.filter(team__zone=zone)[:20] for zone in zones},
        'zones': zones,
    })


def _split_fixtures(matches):
    return {
        'upcoming_matches': matches.filter(status__in=MatchStatus.ACTIVE_STATUSES + (MatchStatus.POSTPONED,)),
        'completed_matches': matches.filter(status=MatchStatus.COMPLETED).order_by('-match_date'),
    }


def team_fixtures(request, team_id):
    """All league fixtures for one team (public, like the main fixtures page)."""
    team = get_object_or_404(Team, pk=team_id)
    matches = (
        Match.objects.filter(Q(home_team=team) | Q(away_team=team))
        .select_related(*FIXTURE_RELATED).order_by('match_date')
    )
    return render(request, 'matches/team_fixtures.html', {'team': team, **_split_fixtures(matches)})


def zone_fixtures(request, zone_id):
    """All league fixtures for one zone (public)."""
    zone = get_object_or_404(Zone, pk=zone_id)
    matches = Match.objects.filter(zone=zone).select_related(*FIXTURE_RELATED).order_by('round_number', 'match_date')
    return render(request, 'matches/zone_fixtures.html', {'zone': zone, **_split_fixtures(matches)})


# ── League admin views ─────────────────────────────────────────────────────

@login_required
@user_passes_test(is_league_admin)
@require_http_methods(['GET', 'POST'])
def admin_edit_match_result(request, match_id):
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), pk=match_id)
    form = MatchResultForm(request.POST or None, instance=match)
    if request.method == 'POST' and form.is_valid():
        match = form.save(commit=False)
        match.status = MatchStatus.COMPLETED
        match.save()  # standings are recalculated by matches.signals
        messages.success(request, 'Match result updated.')
        return redirect('matches:match_details', match_id=match.pk)
    if form.errors:
        messages.error(request, 'Scores must be whole numbers between 0 and 99.')
    return render(request, 'admin_dashboard/edit_match_result.html', {'match': match, 'form': form})


@login_required
@user_passes_test(is_league_admin)
@require_http_methods(['GET', 'POST'])
def admin_edit_league_table(request, table_id):
    table = get_object_or_404(LeagueTable.objects.select_related('team', 'zone'), pk=table_id)
    form = LeagueTableForm(request.POST or None, instance=table)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'League table updated.')
            return redirect('matches:league_tables')
        for error in form.non_field_errors() or ['Please enter non-negative whole numbers.']:
            messages.error(request, error)
    return render(request, 'admin_dashboard/edit_league_table.html', {'table': table, 'form': form})


# ── Match officials ────────────────────────────────────────────────────────

OFFICIAL_ROLES = (
    ('Main Referee', 'main_referee', 'main_confirmed'),
    ('Assistant Referee 1', 'assistant_1', 'ar1_confirmed'),
    ('Assistant Referee 2', 'assistant_2', 'ar2_confirmed'),
    ('Reserve Referee', 'reserve_referee', 'reserve_confirmed'),
    ('VAR', 'var', 'var_confirmed'),
    ('Fourth Official', 'fourth_official', 'fourth_confirmed'),
    ('Match Commissioner', 'match_commissioner', 'commissioner_confirmed'),
)
def _is_officials_staff(user) -> bool:
    return is_any_admin(user) or user.has_perm('referees.appoint_referees')


# Free-text fallbacks used when an official is not a registered Referee.
_FALLBACK = {
    'main_referee': ('main_referee_name', 'main_referee_mobile'),
    'assistant_1': ('ar1_name', 'ar1_mobile'),
    'assistant_2': ('ar2_name', 'ar2_mobile'),
}


@login_required
@require_http_methods(['GET'])
def view_match_officials(request, match_id):
    """
    Officials for a match. Visible to admins/appointers, the appointed
    officials and the two teams' managers; phone numbers only to the first two.
    """
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), pk=match_id)
    officials = (
        MatchOfficials.objects
        .select_related(*(field for _, field, _ in OFFICIAL_ROLES))
        .filter(match=match).first()
    )
    user = request.user
    appointed_user_ids = set()
    if officials:
        for _, field, _ in OFFICIAL_ROLES:
            ref = getattr(officials, field)
            if ref is not None and ref.user_id:
                appointed_user_ids.add(ref.user_id)
    is_staff_side = _is_officials_staff(user)
    is_official = user.pk in appointed_user_ids
    is_team_manager = user.pk in (match.home_team.manager_id, match.away_team.manager_id)
    if not (is_staff_side or is_official or is_team_manager):
        raise PermissionDenied

    show_contacts = is_staff_side or is_official
    rows = []
    if officials:
        for label, field, confirmed_field in OFFICIAL_ROLES:
            ref = getattr(officials, field)
            name_field, phone_field = _FALLBACK.get(field, (None, None))
            name = ref.full_name if ref else (getattr(officials, name_field) if name_field else '')
            phone = ref.phone_number if ref else (getattr(officials, phone_field) if phone_field else '')
            if not name and field not in _FALLBACK:
                continue  # optional roles only listed when appointed
            rows.append({
                'role': label,
                'name': name,
                'phone': phone if show_contacts else '',
                'confirmed': getattr(officials, confirmed_field),
            })
    return render(request, 'matches/view_match_officials.html', {
        'match': match, 'rows': rows, 'show_contacts': show_contacts,
    })
