"""League-staff player management (staff, League Admin, League Manager)."""
import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from fkf_league.permissions import is_league_admin

from ..access import league_staff_required
from ..forms import AdminPlayerForm
from ..models import Player, Team

audit = logging.getLogger('teams.audit')


@league_staff_required
def admin_manage_players(request):
    search_query = request.GET.get('search', '').strip()
    team_filter = request.GET.get('team', '')
    position_filter = request.GET.get('position', '')
    status_filter = request.GET.get('status', '')

    players = Player.objects.select_related('team')
    if search_query:
        players = players.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(id_number__icontains=search_query)
            | Q(fkf_license_number__icontains=search_query)
        )
    if team_filter.isdigit():
        players = players.filter(team_id=int(team_filter))
    if position_filter:
        players = players.filter(position=position_filter)
    if status_filter == 'suspended':
        players = players.filter(is_suspended=True)
    elif status_filter == 'active':
        players = players.filter(is_suspended=False)

    totals = Player.objects.aggregate(
        total_players=Count('id'), suspended_players=Count('id', filter=Q(is_suspended=True))
    )
    return render(request, 'teams/admin_manage_players.html', {
        'players': players.order_by('team__team_name', 'jersey_number'),
        'teams': Team.objects.filter(status=Team.Status.APPROVED).order_by('team_name'),
        'search_query': search_query,
        'team_filter': team_filter,
        'position_filter': position_filter,
        'status_filter': status_filter,
        'position_choices': Player.Position.choices,
        **totals,
    })


@league_staff_required
def admin_delete_player(request, player_id):
    player = get_object_or_404(Player.objects.select_related('team'), pk=player_id)
    if request.method == 'POST':
        name, team_name, pk = player.full_name, player.team.team_name, player.pk
        player.delete()
        audit.info("player %s deleted by user %s", pk, request.user.pk)
        messages.success(request, f'Player {name} deleted successfully from {team_name}')
        return redirect('teams:admin_manage_players')
    return render(request, 'teams/admin_delete_player.html', {'player': player})


@league_staff_required
def admin_suspend_player(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    if request.method == 'POST':
        reason = request.POST.get('suspension_reason', '').strip()
        try:
            matches = int(request.POST.get('suspension_matches', ''))
        except ValueError:
            matches = 0
        if matches < 1 or not reason:
            messages.error(request, 'A positive number of matches and a reason are both required.')
            return redirect('teams:admin_suspend_player', player_id=player_id)
        player.is_suspended = True
        player.suspension_reason = reason
        player.suspension_matches = matches
        player.save(update_fields=['is_suspended', 'suspension_reason', 'suspension_matches'])
        audit.info("player %s suspended for %s matches by user %s", player.pk, matches, request.user.pk)
        messages.success(request, f'{player.full_name} suspended for {matches} match(es).')
        return redirect('teams:admin_manage_players')
    return render(request, 'teams/admin_suspend_player.html', {'player': player})


@league_staff_required
def admin_unsuspend_player(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    if request.method == 'POST':
        player.is_suspended = False
        player.suspension_reason = ''
        player.suspension_end = None
        player.suspension_matches = 0
        player.save(update_fields=['is_suspended', 'suspension_reason', 'suspension_end', 'suspension_matches'])
        audit.info("player %s unsuspended by user %s", player.pk, request.user.pk)
        messages.success(request, f'{player.full_name} unsuspended successfully')
        return redirect('teams:admin_manage_players')
    return render(request, 'teams/admin_unsuspend_player.html', {'player': player})


@league_staff_required
def admin_edit_player(request, player_id):
    """
    Edit player details. Statistics (goals, cards, matches) are normally derived
    from match reports; manual correction is restricted to League Admins and audited.
    """
    player = get_object_or_404(Player, pk=player_id)
    can_edit_stats = is_league_admin(request.user)
    form = AdminPlayerForm(request.POST or None, request.FILES or None, instance=player,
                           can_edit_stats=can_edit_stats)
    if request.method == 'POST':
        if form.is_valid():
            stat_changes = form.changed_stats()
            with transaction.atomic():
                player = form.save()
                if player.is_captain:
                    Player.objects.filter(team=player.team, is_captain=True).exclude(pk=player.pk).update(
                        is_captain=False
                    )
            for field, old, new in stat_changes:
                audit.info("player %s %s corrected %s -> %s by user %s",
                           player.pk, field, old, new, request.user.pk)
            messages.success(request, f'Player {player.full_name} updated successfully')
            return redirect('teams:admin_manage_players')
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}' if field != '__all__' else error)
        player.refresh_from_db()

    return render(request, 'teams/admin_edit_player.html', {
        'player': player,
        'form': form,
        'teams': Team.objects.filter(status=Team.Status.APPROVED).order_by('team_name'),
        'position_choices': Player.Position.choices,
        'can_edit_stats': can_edit_stats,
    })
