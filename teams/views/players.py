"""Player registration for approved teams (team managers, or league staff for any team)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from fkf_league.permissions import is_league_admin_or_manager

from ..access import get_managed_team
from ..forms import PlayerRegistrationForm
from ..models import LeagueSettings, Team
from ..services import register_player


def _registration_closed(request, league):
    return render(request, 'teams/registration_closed.html', {
        'title': 'Player Registration Closed',
        'message': 'Player registration is currently closed. Please check back later '
                   'or contact the league administrator.',
        'deadline': league.player_registration_deadline,
    })


def _resolve_team(request, team_id):
    """
    Returns (team, is_admin, response). League staff pick any approved team via
    ``team_id``; everyone else is limited to the approved team they manage.
    """
    is_admin = is_league_admin_or_manager(request.user)
    if is_admin:
        if not team_id:
            return None, True, None
        return get_object_or_404(Team, pk=team_id, status=Team.Status.APPROVED), True, None

    team = get_managed_team(request.user)
    if not team:
        messages.error(request, "You don't have an approved team.")
        return None, False, redirect('dashboard')
    if not team.kit_colors_set:
        messages.error(request, "Please set your team kit colors first!")
        return None, False, redirect('teams:select_kit_colors')
    return team, False, None


def _page(request, team, is_admin, form=None, status=200):
    players = team.players.order_by('jersey_number')
    return render(request, 'teams/add_players_approved.html', {
        'team': team,
        'players': players,
        'player_count': players.count(),
        'suspended_players': [pl for pl in players if pl.is_suspended],
        'is_admin': is_admin,
        'form': form or PlayerRegistrationForm(team=team),
        'position_choices': PlayerRegistrationForm.base_fields['position'].choices,
    }, status=status)


@login_required
def add_players_to_approved_team(request):
    league = LeagueSettings.get_settings()
    is_admin = is_league_admin_or_manager(request.user)
    if not league.player_registration_open and not is_admin:
        return _registration_closed(request, league)

    team, is_admin, response = _resolve_team(request, request.GET.get('team_id'))
    if response:
        return response
    if team is None:  # league staff: choose a team first
        return render(request, 'teams/admin_select_team_players.html', {
            'teams': Team.objects.filter(status=Team.Status.APPROVED).order_by('team_name'),
        })
    return _page(request, team, is_admin)


@login_required
@require_POST
def add_player_action(request):
    league = LeagueSettings.get_settings()
    is_admin = is_league_admin_or_manager(request.user)
    if not league.player_registration_open and not is_admin:
        return _registration_closed(request, league)

    team, is_admin, response = _resolve_team(request, request.POST.get('team_id') or request.GET.get('team_id'))
    if response:
        return response
    if team is None:
        return redirect('teams:add_players_approved')

    form = PlayerRegistrationForm(request.POST, request.FILES, team=team)
    if not form.is_valid():
        messages.error(request, 'Player was not added - please correct the errors below.')
        return _page(request, team, is_admin, form=form, status=400)

    player = register_player(form, team)
    messages.success(request, f'Player {player.full_name} added successfully!')
    url = reverse('teams:add_players_approved')
    return redirect(f'{url}?team_id={team.id}' if is_admin else url)
