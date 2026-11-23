"""Matchday squads: team managers submit, appointed referees approve."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from referees.models import Referee

from ..models import (
    TournamentMatch,
    TournamentMatchdaySquad,
    TournamentMatchOfficials,
    TournamentTeamRegistration,
)
from ..services import eligible_squad_players, player_field_for, submit_matchday_squad

logger = logging.getLogger(__name__)

APPROVED = TournamentTeamRegistration.Status.APPROVED
SquadStatus = TournamentMatchdaySquad.Status


def _user_registrations(user):
    """Approved registrations for league teams or external teams the user manages."""
    return TournamentTeamRegistration.objects.filter(
        Q(team__manager=user) | Q(external_team__manager_user=user), status=APPROVED,
    )


def _user_registration_for_match(user, match) -> TournamentTeamRegistration | None:
    team_ids = [pk for pk in (match.home_team_id, match.away_team_id) if pk]
    return _user_registrations(user).filter(pk__in=team_ids).select_related('team', 'external_team').first()


def _referee_for(user) -> Referee | None:
    return Referee.objects.filter(user=user).first()


# ── Team manager ───────────────────────────────────────────────────────────
@login_required
def tournament_team_matches(request):
    """Upcoming tournament matches for every team the user manages."""
    regs = list(_user_registrations(request.user).select_related('tournament', 'team', 'external_team'))
    matches = (
        TournamentMatch.objects
        .filter(Q(home_team__in=regs) | Q(away_team__in=regs), status=TournamentMatch.Status.SCHEDULED)
        .select_related('tournament', 'home_team__team', 'home_team__external_team',
                        'away_team__team', 'away_team__external_team')
        .order_by('match_date')
    )
    squads = {
        (s.match_id, s.team_registration_id): s
        for s in TournamentMatchdaySquad.objects.filter(match__in=matches, team_registration__in=regs)
        .annotate(starting=Count('squad_players', filter=Q(squad_players__is_starting=True)),
                  subs=Count('squad_players', filter=Q(squad_players__is_starting=False)))
    }
    matches_data = []
    for m in matches:
        for reg in regs:
            if reg.pk in (m.home_team_id, m.away_team_id):
                squad = squads.get((m.pk, reg.pk))
                matches_data.append({
                    'match': m, 'reg': reg, 'squad': squad,
                    'starting_count': squad.starting if squad else 0,
                    'subs_count': squad.subs if squad else 0,
                })
    return render(request, 'tournaments/team_tournament_matches.html', {'matches_data': matches_data})


@login_required
@require_http_methods(['GET', 'POST'])
def tournament_submit_squad(request, match_pk):
    """Team manager submits the matchday squad for their own team only."""
    match = get_object_or_404(TournamentMatch.objects.select_related('tournament'), pk=match_pk)
    reg = _user_registration_for_match(request.user, match)
    if not reg:
        messages.error(request, 'Your team is not playing in this match.')
        return redirect('tournaments:tournament_team_matches')

    # Not created until something is submitted (no writes on GET).
    squad = TournamentMatchdaySquad.objects.filter(match=match, team_registration=reg).first() \
        or TournamentMatchdaySquad(match=match, team_registration=reg)
    can_edit = squad.can_edit() and match.status == TournamentMatch.Status.SCHEDULED
    field = player_field_for(reg)

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, 'This squad can no longer be changed.')
            return redirect('tournaments:tournament_team_matches')
        errors = submit_matchday_squad(
            squad,
            request.POST.getlist('starting_players'),
            request.POST.getlist('substitute_players'),
            request.user,
        )
        if not errors:
            logger.info('Tournament squad submitted: squad=%s user=%s', squad.pk, request.user.pk)
            messages.success(request, 'Squad submitted! Awaiting referee approval.')
            return redirect('tournaments:tournament_team_matches')
        for error in errors:
            messages.error(request, error)

    selected_starting, selected_subs = [], []
    if squad.pk:
        for player_id, is_starting in squad.squad_players.values_list(f'{field}_id', 'is_starting'):
            (selected_starting if is_starting else selected_subs).append(player_id)

    return render(request, 'tournaments/tournament_submit_squad.html', {
        'match': match,
        'squad': squad,
        'reg': reg,
        'eligible_players': eligible_squad_players(reg),
        'selected_starting': selected_starting,
        'selected_subs': selected_subs,
        'can_edit': can_edit,
        'player_field': field,
    })


# ── Referee ────────────────────────────────────────────────────────────────
@login_required
def tournament_referee_squad_list(request):
    """Squads for the scheduled tournament matches this referee is appointed to."""
    referee = _referee_for(request.user)
    if referee is None:
        messages.error(request, 'You are not registered as a referee.')
        return redirect('dashboard')

    appointed = (
        TournamentMatch.objects
        .filter(Q(officials__main_referee=referee) | Q(officials__assistant_1=referee)
                | Q(officials__assistant_2=referee) | Q(officials__fourth_official=referee),
                status=TournamentMatch.Status.SCHEDULED)
        .distinct()
        .select_related('tournament', 'home_team__team', 'home_team__external_team',
                        'away_team__team', 'away_team__external_team')
        .prefetch_related('matchday_squads__team_registration__team',
                          'matchday_squads__team_registration__external_team')
    )
    matches_data = []
    for m in appointed:
        squads = list(m.matchday_squads.all())
        matches_data.append({
            'match': m,
            'squads': squads,
            'pending_count': sum(s.status == SquadStatus.SUBMITTED for s in squads),
        })
    return render(request, 'tournaments/tournament_referee_squads.html', {'matches_data': matches_data})


@login_required
@require_http_methods(['GET', 'POST'])
def tournament_approve_squad(request, squad_pk):
    """An appointed referee approves or returns a submitted squad."""
    squad = get_object_or_404(
        TournamentMatchdaySquad.objects.select_related(
            'match__tournament', 'team_registration__team', 'team_registration__external_team',
        ),
        pk=squad_pk,
    )
    referee = _referee_for(request.user)
    if referee is None:
        messages.error(request, 'You are not registered as a referee.')
        return redirect('dashboard')
    officials = TournamentMatchOfficials.objects.filter(match=squad.match).first()
    if officials is None or not officials.involves(referee):
        raise PermissionDenied

    if request.method == 'POST':
        action = request.POST.get('action')
        name = squad.team_registration.display_name
        if squad.status != SquadStatus.SUBMITTED:
            messages.error(request, 'Only submitted squads can be reviewed.')
        elif action == 'approve':
            squad.status = SquadStatus.APPROVED
            squad.approved_at = timezone.now()
            squad.approved_by = referee
            squad.save(update_fields=['status', 'approved_at', 'approved_by', 'updated_at'])
            messages.success(request, f'Squad for {name} approved.')
        elif action == 'reject':
            squad.status = SquadStatus.PENDING
            squad.save(update_fields=['status', 'updated_at'])
            messages.warning(request, f'Squad for {name} sent back for revision.')
        else:
            messages.error(request, 'Unknown action.')
        logger.info('Tournament squad review: squad=%s action=%s referee=%s', squad.pk, action, referee.pk)
        return redirect('tournaments:tournament_referee_squad_list')

    return render(request, 'tournaments/tournament_approve_squad.html', {
        'squad': squad,
        'match': squad.match,
        'starting': squad.get_starting_eleven().select_related('player', 'external_player'),
        'subs': squad.get_substitutes().select_related('player', 'external_player'),
    })
