"""Team dashboards, team lists and team detail pages."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from fkf_league.permissions import is_league_admin_or_manager
from payments.models import Payment
from tournaments.models import (
    Tournament,
    TournamentMatch,
    TournamentMatchdaySquad,
    TournamentTeamRegistration,
)

from ..access import ensure_can_view_team, get_managed_team, league_staff_required
from ..forms import TeamEditForm
from ..models import Player, Team, Zone
from ..utils import get_match_squad_data


def _tournament_context(team, manager):
    """Tournament registrations for ``team`` and for external teams run by ``manager``."""
    team_regs = TournamentTeamRegistration.objects.filter(team=team).select_related('tournament')
    external_regs = TournamentTeamRegistration.objects.none()
    if manager is not None:
        external_regs = (
            TournamentTeamRegistration.objects
            .filter(external_team__manager_user=manager)
            .select_related('tournament', 'external_team')
        )
    open_tournaments = (
        Tournament.objects
        .filter(status='registration', registration_deadline__gte=timezone.now())
        .exclude(registrations__team=team)
    )
    return {
        'team_tournament_regs': team_regs,
        'external_tournament_regs': external_regs,
        'open_tournaments': open_tournaments,
    }


@login_required
def team_dashboard(request, team_id):
    """Team dashboard for league staff (any team) or the team's own manager."""
    team = get_object_or_404(Team.objects.select_related('zone', 'manager'), pk=team_id)
    ensure_can_view_team(request.user, team)

    current_round, matches_data = get_match_squad_data(team)
    return render(request, 'teams/dashboard.html', {
        'team': team,
        'players': team.players.order_by('jersey_number'),
        'payments': Payment.objects.filter(team=team),
        'upcoming_matches': matches_data,
        'current_round': current_round,
        **_tournament_context(team, team.manager),
    })


@login_required
def team_manager_dashboard(request):
    """Dashboard for the manager of an approved team."""
    team = get_managed_team(request.user)
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')

    show_kit_prompt = not team.kit_colors_set and not team.kit_setup_prompt_shown
    if show_kit_prompt:
        team.kit_setup_prompt_shown = True
        team.save(update_fields=['kit_setup_prompt_shown'])

    current_round, matches_data = get_match_squad_data(team)
    players = team.players.order_by('jersey_number')
    captain = players.filter(is_captain=True).first()

    approved_regs = TournamentTeamRegistration.objects.filter(
        Q(team=team) | Q(external_team__manager_user=request.user), status='approved'
    )
    tournament_matches = (
        TournamentMatch.objects
        .filter(Q(home_team__in=approved_regs) | Q(away_team__in=approved_regs), status='scheduled')
        .select_related('tournament', 'home_team', 'away_team')
        .prefetch_related(Prefetch(
            'matchday_squads',
            queryset=TournamentMatchdaySquad.objects.annotate(
                starting_count=Count('squad_players', filter=Q(squad_players__is_starting=True)),
                subs_count=Count('squad_players', filter=Q(squad_players__is_starting=False)),
            ),
        ))
        .order_by('match_date')
    )
    approved_reg_ids = set(approved_regs.values_list('pk', flat=True))
    tournament_matches_data = []
    for tm in tournament_matches:
        for reg in (tm.home_team, tm.away_team):
            if reg is None or reg.pk not in approved_reg_ids:
                continue
            squad = next((s for s in tm.matchday_squads.all() if s.team_registration_id == reg.pk), None)
            tournament_matches_data.append({
                'match': tm,
                'reg': reg,
                'squad': squad,
                'starting_count': squad.starting_count if squad else 0,
                'subs_count': squad.subs_count if squad else 0,
            })

    return render(request, 'dashboard/team_manager.html', {
        'team': team,
        'players': players,
        'player_count': players.count(),
        'captain_name': captain.full_name if captain else 'Not set',
        'kit_complete': team.kit_colors_set,
        'show_kit_prompt': show_kit_prompt,
        'recent_players': players.order_by('-registration_date')[:10],
        'upcoming_matches': matches_data,
        'current_round': current_round,
        'tournament_matches_data': tournament_matches_data,
        **_tournament_context(team, request.user),
    })


@league_staff_required
def league_admin_dashboard(request):
    """Team/player overview for league staff."""
    stats = Team.objects.aggregate(
        teams_count=Count('id'),
        active_teams=Count('id', filter=Q(status=Team.Status.APPROVED)),
        pending_teams=Count('id', filter=Q(status=Team.Status.PENDING)),
        paid_teams=Count('id', filter=Q(payment_status=True)),
        unpaid_teams=Count('id', filter=Q(payment_status=False)),
        recent_registrations=Count('id', filter=Q(registration_date__gte=timezone.now() - timedelta(days=7))),
    )
    stats.update(Player.objects.aggregate(
        total_players=Count('id'),
        total_captains=Count('id', filter=Q(is_captain=True)),
    ))
    return render(request, 'teams/admin_dashboard.html', {
        **stats,
        'recent_teams': Team.objects.select_related('zone').order_by('-registration_date')[:10],
    })


@league_staff_required
def all_teams(request):
    return render(request, 'teams/all_teams.html', {
        'teams': Team.objects.select_related('zone'),
        'zones': Zone.objects.all(),
    })


@login_required
def team_detail(request, team_id):
    """Team details (contact, payment, squad) for league staff or the team's own manager."""
    team = get_object_or_404(Team.objects.select_related('zone'), pk=team_id)
    ensure_can_view_team(request.user, team)
    return render(request, 'teams/team_detail.html', {
        'team': team,
        'can_edit': is_league_admin_or_manager(request.user),
        'players': team.players.order_by('jersey_number'),
    })


@league_staff_required
def edit_team_info(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    form = TeamEditForm(request.POST or None, request.FILES or None, instance=team)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Team info updated successfully.')
            return redirect('teams:team_detail', team_id=team.id)
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'teams/edit_team_info.html', {'form': form, 'team': team})
