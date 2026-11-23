"""Staff-only match management screens (templates live in templates/admin_dashboard/)."""
import logging
from datetime import date, datetime, time

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from teams.models import Team, Zone

from . import services
from .models import Match
from .utils.fixture_generator import update_match_date

logger = logging.getLogger(__name__)


def _rounds():
    return Match.objects.values_list('round_number', flat=True).distinct().order_by('round_number')


def _parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class _InvalidMatchData(ValueError):
    pass


def _aware_kickoff(match_day: date, kickoff: str | None) -> datetime:
    """Aware datetime for a local match day + optional validated 'HH:MM' kickoff."""
    kickoff_time = time.fromisoformat(kickoff) if kickoff else time(0, 0)
    return timezone.make_aware(datetime.combine(match_day, kickoff_time))


def _clean_match_post(post) -> dict:
    """Validate the create/edit match form. Raises _InvalidMatchData with a user-safe message."""
    home = Team.objects.filter(pk=_parse_int(post.get('home_team'))).first()
    away = Team.objects.filter(pk=_parse_int(post.get('away_team'))).first()
    zone = Zone.objects.filter(pk=_parse_int(post.get('zone'))).first()
    if not (home and away and zone):
        raise _InvalidMatchData('Select a valid home team, away team and zone.')
    if home.pk == away.pk:
        raise _InvalidMatchData('Home team and away team cannot be the same.')
    try:
        match_day = date.fromisoformat(post.get('match_date', ''))
    except ValueError as exc:
        raise _InvalidMatchData('Enter a valid match date.') from exc
    kickoff = (post.get('kickoff_time') or '').strip()[:5] or None
    if kickoff:
        try:
            time.fromisoformat(kickoff)
        except ValueError as exc:
            raise _InvalidMatchData('Kickoff time must be HH:MM.') from exc
    status = post.get('status') or Match.Status.SCHEDULED
    if status not in Match.Status.values:
        raise _InvalidMatchData('Invalid status.')
    round_number = _parse_int(post.get('round_number'), 1)
    if round_number < 1:
        raise _InvalidMatchData('Round must be 1 or higher.')
    return {
        'home_team': home, 'away_team': away, 'zone': zone, 'match_day': match_day,
        'kickoff_time': kickoff,
        'venue': (post.get('venue') or '').strip()[:200] or home.home_ground,
        'round_number': round_number, 'status': status,
    }


@staff_member_required
@require_http_methods(['GET', 'POST'])
def reschedule_match(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    if request.method == 'POST':
        new_kickoff = request.POST.get('new_kickoff_time')
        success, message = update_match_date(match.pk, request.POST.get('new_date'), new_kickoff, new_kickoff)
        if success:
            new_round = _parse_int(request.POST.get('new_round'))
            if new_round and new_round != match.round_number:
                swapped = services.move_match_to_round(match, new_round)
                message += f' | Round changed to {new_round}'
                if swapped:
                    message += f' (swapped with match {swapped.pk})'
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect('matches:match_details', match_id=match.pk)
    return render(request, 'admin_dashboard/reschedule_single.html', {'match': match, 'rounds': _rounds()})


@staff_member_required
@require_http_methods(['GET', 'POST'])
def move_match_round(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    if request.method == 'POST':
        new_round = _parse_int(request.POST.get('new_round'))
        if not new_round or new_round < 1:
            messages.error(request, 'Choose a valid round.')
            return redirect('matches:move_match_round', match_id=match.pk)
        if new_round == match.round_number:
            messages.info(request, 'No change in round.')
        else:
            swapped = services.move_match_to_round(match, new_round)
            suffix = f' and swapped with match {swapped.pk}' if swapped else ''
            messages.success(request, f'Match moved to round {new_round}{suffix}.')
        return redirect('matches:manage_matches')
    return render(request, 'admin_dashboard/move_match_round.html', {'match': match, 'rounds': _rounds()})


@staff_member_required
@require_http_methods(['GET'])
def manage_matches(request):
    zone_filter = request.GET.get('zone', '')
    status_filter = request.GET.get('status', '')
    round_filter = request.GET.get('round', '')
    search_query = request.GET.get('search', '').strip()

    matches = Match.objects.select_related('home_team', 'away_team', 'zone')
    if zone_filter.isdigit():
        matches = matches.filter(zone_id=int(zone_filter))
    if status_filter in Match.Status.values:
        matches = matches.filter(status=status_filter)
    if round_filter.isdigit():
        matches = matches.filter(round_number=int(round_filter))
    if search_query:
        matches = matches.filter(
            Q(home_team__team_name__icontains=search_query)
            | Q(away_team__team_name__icontains=search_query)
            | Q(venue__icontains=search_query)
        )

    counts = Match.objects.aggregate(
        total_count=Count('id'),
        scheduled_count=Count('id', filter=Q(status=Match.Status.SCHEDULED)),
        completed_count=Count('id', filter=Q(status=Match.Status.COMPLETED)),
        postponed_count=Count('id', filter=Q(status=Match.Status.POSTPONED)),
    )
    return render(request, 'admin_dashboard/manage_matches.html', {
        'matches': matches.order_by('-match_date'),
        'zones': Zone.objects.all(),
        'rounds': _rounds(),
        'selected_zone': zone_filter,
        'selected_status': status_filter,
        'selected_round': round_filter,
        'search_query': search_query,
        'status_choices': Match.STATUS_CHOICES,
        **counts,
    })


def _match_form_context(**extra):
    return {
        'zones': Zone.objects.all(),
        'teams': Team.objects.filter(status='approved').order_by('team_name'),
        'status_choices': Match.STATUS_CHOICES,
        **extra,
    }


@staff_member_required
@require_http_methods(['GET', 'POST'])
def create_match(request):
    if request.method == 'POST':
        try:
            data = _clean_match_post(request.POST)
        except _InvalidMatchData as exc:
            messages.error(request, str(exc))
            return redirect('matches:create_match')
        match = Match.objects.create(
            home_team=data['home_team'], away_team=data['away_team'], zone=data['zone'],
            match_date=_aware_kickoff(data['match_day'], data['kickoff_time']),
            kickoff_time=data['kickoff_time'], venue=data['venue'],
            round_number=data['round_number'], status=data['status'],
        )
        logger.info("Match %s created by user %s", match.pk, request.user.pk)
        messages.success(request, f'Match created: {match.home_team.team_name} vs {match.away_team.team_name}')
        return redirect('matches:manage_matches')
    return render(request, 'admin_dashboard/create_match.html', _match_form_context())


@staff_member_required
@require_http_methods(['GET', 'POST'])
def edit_match(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    if request.method == 'POST':
        try:
            data = _clean_match_post(request.POST)
            home_score = _parse_int(request.POST.get('home_score'), 0)
            away_score = _parse_int(request.POST.get('away_score'), 0)
            if home_score < 0 or away_score < 0:
                raise _InvalidMatchData('Scores cannot be negative.')
        except _InvalidMatchData as exc:
            messages.error(request, str(exc))
            return redirect('matches:edit_match', match_id=match.pk)

        if data['round_number'] != match.round_number:
            services.move_match_to_round(match, data['round_number'])
        match.home_team = data['home_team']
        match.away_team = data['away_team']
        match.zone = data['zone']
        match.match_date = _aware_kickoff(data['match_day'], data['kickoff_time'])
        match.kickoff_time = data['kickoff_time']
        match.venue = data['venue']
        match.status = data['status']
        match.home_score = home_score
        match.away_score = away_score
        match.save()  # standings refreshed by matches.signals
        logger.info("Match %s edited by user %s", match.pk, request.user.pk)
        messages.success(request, 'Match updated.')
        return redirect('matches:manage_matches')
    return render(request, 'admin_dashboard/edit_match.html', _match_form_context(
        match=match,
        match_date_str=timezone.localtime(match.match_date).strftime('%Y-%m-%d'),
    ))


@staff_member_required
@require_http_methods(['GET', 'POST'])
def delete_match(request, match_id):
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), pk=match_id)
    if request.method == 'POST':
        info = f"{match.home_team.team_name} vs {match.away_team.team_name}"
        logger.info("Match %s deleted by user %s", match.pk, request.user.pk)
        match.delete()
        messages.success(request, f'Match deleted: {info}')
        return redirect('matches:manage_matches')
    return render(request, 'admin_dashboard/delete_match.html', {'match': match})

