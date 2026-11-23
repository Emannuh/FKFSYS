"""Club-to-club transfer requests between team managers."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..access import get_managed_team
from ..models import LeagueSettings, Player, Team, TransferRequest
from .. import services


def _window_closed(request, league):
    return render(request, 'teams/registration_closed.html', {
        'title': 'Transfer Window Closed',
        'message': 'Player transfers are currently closed. Please check back once the window reopens.',
        'deadline': league.transfer_window_deadline,
    })


def _no_team(request):
    messages.error(request, "You don't have an approved team.")
    return redirect('dashboard')


@login_required
def search_players(request):
    """Pick another approved team and request one of its players."""
    team = get_managed_team(request.user)
    if not team:
        return _no_team(request)
    league = LeagueSettings.get_settings()
    if not league.transfer_window_open:
        return _window_closed(request, league)

    other_teams = (
        Team.objects.filter(status=Team.Status.APPROVED).exclude(pk=team.pk)
        .select_related('zone').order_by('team_name')
    )
    selected_team_id = request.GET.get('team_id', '')
    selected_players = Player.objects.none()
    if selected_team_id.isdigit():
        selected_players = Player.objects.filter(
            team__in=other_teams, team_id=int(selected_team_id)
        ).order_by('jersey_number')

    return render(request, 'teams/search_players.html', {
        'team': team,
        'all_teams': other_teams,
        'selected_team_id': selected_team_id,
        'selected_players': selected_players,
        'transfer_window_open': league.transfer_window_open,
    })


@login_required
@require_POST
def request_transfer(request, player_id):
    league = LeagueSettings.get_settings()
    if not league.transfer_window_open:
        return _window_closed(request, league)
    to_team = get_managed_team(request.user)
    if not to_team:
        return _no_team(request)
    player = get_object_or_404(
        Player.objects.select_related('team'), pk=player_id, team__status=Team.Status.APPROVED
    )
    try:
        services.request_transfer(player, to_team, request.user)
    except services.TransferError as exc:
        messages.error(request, str(exc))
        return redirect('teams:search_players')
    messages.success(
        request,
        f"Transfer requested for {player.full_name} (#{player.jersey_number}) from "
        f"{player.team.team_name}. It is now awaiting that club's decision.",
    )
    return redirect('teams:my_transfer_requests')


@login_required
def my_transfer_requests(request):
    team = get_managed_team(request.user)
    if not team:
        return _no_team(request)
    outgoing = (
        TransferRequest.objects.filter(to_team=team)
        .select_related('player', 'from_team', 'requested_by').order_by('-request_date')
    )
    incoming = (
        TransferRequest.objects.filter(from_team=team, status=TransferRequest.Status.PENDING_PARENT)
        .select_related('player', 'to_team', 'requested_by').order_by('-request_date')
    )
    return render(request, 'teams/transfer_requests.html', {
        'team': team,
        'outgoing_requests': outgoing,
        'incoming_requests': incoming,
        'pending_incoming_count': incoming.count(),
    })


@login_required
@require_POST
def approve_transfer(request, transfer_id):
    get_object_or_404(TransferRequest, pk=transfer_id)
    try:
        transfer = services.approve_transfer(transfer_id, request.user, get_managed_team(request.user))
    except services.TransferError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request, f"Transfer approved! {transfer.player.full_name} has moved to {transfer.to_team.team_name}."
        )
    return redirect('teams:my_transfer_requests')


@login_required
def reject_transfer(request, transfer_id):
    """GET shows the reason form; POST rejects."""
    transfer = get_object_or_404(TransferRequest.objects.select_related('player', 'to_team'), pk=transfer_id)
    team = get_managed_team(request.user)
    if team is None or transfer.from_team_id != team.pk:
        messages.error(request, "You can only reject transfers for your own team.")
        return redirect('teams:my_transfer_requests')
    if transfer.status != TransferRequest.Status.PENDING_PARENT:
        messages.error(request, "This transfer request has already been processed.")
        return redirect('teams:my_transfer_requests')

    if request.method == 'POST':
        try:
            services.reject_transfer(transfer_id, request.user, team, request.POST.get('reason', ''))
        except services.TransferError as exc:
            messages.error(request, str(exc))
            return redirect('teams:reject_transfer', transfer_id=transfer_id)
        messages.success(request, f"Transfer rejected. {transfer.to_team.team_name} has been notified.")
        return redirect('teams:my_transfer_requests')

    return render(request, 'teams/reject_transfer.html', {'transfer': transfer, 'team': team})


@login_required
@require_POST
def cancel_transfer(request, transfer_id):
    get_object_or_404(TransferRequest, pk=transfer_id)
    try:
        transfer = services.cancel_transfer(transfer_id, request.user, get_managed_team(request.user))
    except services.TransferError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Transfer request for {transfer.player.full_name} cancelled.")
    return redirect('teams:my_transfer_requests')
