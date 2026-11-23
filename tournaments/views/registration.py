"""Team and player registration (league team managers and external teams)."""
import logging
import re

from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from teams.models import Team

from ..access import is_tournament_admin
from ..forms import ExternalPlayerForm, ExternalTeamForm, PlayerRegistrationForm, TeamRegistrationForm
from ..models import ExternalTeam, TournamentPlayerRegistration, TournamentTeamRegistration
from .public import get_visible_tournament

logger = logging.getLogger(__name__)

APPROVED = TournamentTeamRegistration.Status.APPROVED
TeamType = TournamentTeamRegistration.TeamType


def _is_full(tournament) -> bool:
    return tournament.registrations.filter(status=APPROVED).count() >= tournament.max_teams


def _unique_username(seed: str) -> str:
    User = get_user_model()
    base = re.sub(r'[^a-z0-9]', '', seed.lower())[:20] or 'team'
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username = f'{base}{n}'
        n += 1
    return username


# ── League team registration ───────────────────────────────────────────────
@login_required
def register_team(request, slug):
    """Team manager registers their own approved league team."""
    tournament = get_visible_tournament(request, slug)
    if not tournament.is_registration_open:
        messages.error(request, 'Registration is closed for this tournament.')
        return redirect('tournaments:tournament_detail', slug=slug)

    team = Team.objects.filter(manager=request.user, status='approved').first()
    if not team:
        messages.error(request, 'You must manage an approved team to register.')
        return redirect('tournaments:tournament_detail', slug=slug)
    if TournamentTeamRegistration.objects.filter(tournament=tournament, team=team).exists():
        messages.info(request, 'Your team is already registered for this tournament.')
        return redirect('tournaments:tournament_detail', slug=slug)
    if _is_full(tournament):
        messages.error(request, 'This tournament has reached maximum capacity.')
        return redirect('tournaments:tournament_detail', slug=slug)

    form = TeamRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        _, created = TournamentTeamRegistration.objects.get_or_create(
            tournament=tournament, team=team,
            defaults={'team_type': TeamType.LEAGUE, 'registered_by': request.user},
        )
        if created:
            messages.success(request, f'{team.team_name} registered. Awaiting admin approval.')
        return redirect('tournaments:tournament_detail', slug=slug)
    return render(request, 'tournaments/register_team.html', {
        'tournament': tournament, 'team': team, 'form': form,
    })


# ── External team registration (public portal) ─────────────────────────────
def register_external_team(request, slug):
    """Public portal for teams outside the league.

    Anonymous visitors get a new portal account (Team Managers group) with the
    password they choose; an email that already has an account must log in
    first. Logged-in users register the team under their own account.
    """
    tournament = get_visible_tournament(request, slug)
    if not tournament.allow_external_teams:
        messages.error(request, 'This tournament does not accept external teams.')
        return redirect('tournaments:tournament_detail', slug=slug)
    if not tournament.is_registration_open:
        messages.error(request, 'Registration is closed for this tournament.')
        return redirect('tournaments:tournament_detail', slug=slug)
    if _is_full(tournament):
        messages.error(request, 'This tournament has reached maximum capacity.')
        return redirect('tournaments:tournament_detail', slug=slug)

    form = ExternalTeamForm(request.POST or None, request.FILES or None,
                            tournament=tournament, user=request.user)
    if request.method == 'POST' and form.is_valid():
        new_account = not request.user.is_authenticated
        with transaction.atomic():
            if new_account:
                names = form.cleaned_data['contact_person'].split()
                manager = get_user_model().objects.create_user(
                    username=_unique_username(form.cleaned_data['team_name']),
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['manager_password'],
                    first_name=names[0] if names else '',
                    last_name=' '.join(names[1:]),
                )
                manager.groups.add(Group.objects.get_or_create(name='Team Managers')[0])
            else:
                manager = request.user
            ext_team = form.save(commit=False)
            ext_team.tournament = tournament
            ext_team.manager_user = manager
            ext_team.save()
            TournamentTeamRegistration.objects.create(
                tournament=tournament, external_team=ext_team,
                team_type=TeamType.EXTERNAL, registered_by=manager,
            )
        logger.info('External team registered: tournament=%s team=%s user=%s new_account=%s',
                    tournament.pk, ext_team.pk, manager.pk, new_account)
        if new_account:
            auth_login(request, manager)
            messages.info(request, f'Your portal account was created. Username: {manager.username}')
        messages.success(request, f'{ext_team.team_name} registered for {tournament.name}. Awaiting admin approval.')
        return redirect('tournaments:tournament_detail', slug=slug)
    return render(request, 'tournaments/register_external_team.html', {'tournament': tournament, 'form': form})


# ── Player registration ────────────────────────────────────────────────────
@login_required
def register_players(request, slug):
    """Team manager adds league players from their roster to the tournament squad."""
    tournament = get_visible_tournament(request, slug)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    if not team:
        messages.error(request, 'You must manage an approved team.')
        return redirect('tournaments:tournament_detail', slug=slug)
    team_reg = TournamentTeamRegistration.objects.filter(
        tournament=tournament, team=team, status=APPROVED,
    ).first()
    if not team_reg:
        messages.error(request, 'Your team must be approved for this tournament first.')
        return redirect('tournaments:tournament_detail', slug=slug)

    squad = team_reg.player_registrations.select_related('player')
    form = PlayerRegistrationForm(request.POST or None, team=team, tournament=tournament)
    if request.method == 'POST' and form.is_valid():
        selected = list(form.cleaned_data['players'])
        with transaction.atomic():
            current = squad.select_for_update().count()
            if current + len(selected) > tournament.max_squad_size:
                messages.error(request, f'Max squad size is {tournament.max_squad_size}. '
                                        f'You already have {current} players.')
            else:
                TournamentPlayerRegistration.objects.bulk_create(
                    TournamentPlayerRegistration(
                        tournament=tournament, team_registration=team_reg,
                        player=p, jersey_number=p.jersey_number,
                    ) for p in selected
                )
                messages.success(request, f'{len(selected)} player(s) added to squad.')
                return redirect('tournaments:register_players', slug=slug)
    return render(request, 'tournaments/register_players.html', {
        'tournament': tournament, 'team': team, 'team_reg': team_reg, 'squad': squad, 'form': form,
    })


@login_required
def register_external_players(request, slug, ext_team_pk):
    """Manager of an external team (or an admin) adds players one by one."""
    tournament = get_visible_tournament(request, slug)
    ext_team = get_object_or_404(ExternalTeam, pk=ext_team_pk, tournament=tournament)
    if ext_team.manager_user_id != request.user.pk and not is_tournament_admin(request.user):
        raise PermissionDenied

    team_reg = TournamentTeamRegistration.objects.filter(
        tournament=tournament, external_team=ext_team, status=APPROVED,
    ).first()
    if not team_reg:
        messages.error(request, 'This team must be approved before adding players.')
        return redirect('tournaments:tournament_detail', slug=slug)

    squad = team_reg.player_registrations.select_related('external_player')
    form = ExternalPlayerForm(request.POST or None, request.FILES or None, external_team=ext_team)
    if request.method == 'POST' and form.is_valid():
        if squad.count() >= tournament.max_squad_size:
            messages.error(request, f'Squad is full ({tournament.max_squad_size} players max).')
        else:
            with transaction.atomic():
                ext_player = form.save(commit=False)
                ext_player.external_team = ext_team
                ext_player.save()
                TournamentPlayerRegistration.objects.create(
                    tournament=tournament, team_registration=team_reg,
                    external_player=ext_player, jersey_number=ext_player.jersey_number,
                )
            messages.success(request, f'{ext_player.full_name} added to squad.')
            return redirect('tournaments:register_external_players', slug=slug, ext_team_pk=ext_team.pk)
    return render(request, 'tournaments/register_external_players.html', {
        'tournament': tournament, 'ext_team': ext_team, 'team_reg': team_reg, 'squad': squad, 'form': form,
    })
