"""
teams/services.py

Business operations shared by views (and usable from other apps / admin).
"""
from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import Player, Team, TransferRequest

audit = logging.getLogger('teams.audit')


class TransferError(Exception):
    """A transfer action is not allowed in the request's current state."""


@transaction.atomic
def register_player(form, team: Team) -> Player:
    """Save a validated PlayerRegistrationForm to ``team``; a new captain replaces the old one."""
    player = form.save(commit=False)
    player.team = team
    if player.is_captain:
        Player.objects.filter(team=team, is_captain=True).update(is_captain=False)
    player.save()
    return player


def _locked_transfer(transfer_id: int) -> TransferRequest:
    return (
        TransferRequest.objects.select_for_update()
        .select_related('player', 'from_team', 'to_team')
        .get(pk=transfer_id)
    )


@transaction.atomic
def approve_transfer(transfer_id: int, user, team: Team | None) -> TransferRequest:
    """Parent club (``team``) approves and executes a pending transfer."""
    transfer = _locked_transfer(transfer_id)
    if team is None or transfer.from_team_id != team.pk:
        raise PermissionDenied
    if transfer.status != TransferRequest.Status.PENDING_PARENT:
        raise TransferError('This transfer request has already been processed.')
    if transfer.player.team_id != transfer.from_team_id:
        # The player has moved since the request was made — the request is stale.
        transfer.status = TransferRequest.Status.CANCELLED
        transfer.save()
        raise TransferError('This player is no longer registered with your team; the request was cancelled.')
    transfer.approve_by_parent(user=user, execute_transfer=True)
    audit.info("transfer %s approved by user %s", transfer.pk, user.pk)
    return transfer


@transaction.atomic
def reject_transfer(transfer_id: int, user, team: Team | None, reason: str) -> TransferRequest:
    transfer = _locked_transfer(transfer_id)
    if team is None or transfer.from_team_id != team.pk:
        raise PermissionDenied
    if transfer.status != TransferRequest.Status.PENDING_PARENT:
        raise TransferError('This transfer request has already been processed.')
    if not reason.strip():
        raise TransferError('Please provide a reason for rejection.')
    transfer.reject_by_parent(user=user, reason=reason.strip())
    audit.info("transfer %s rejected by user %s", transfer.pk, user.pk)
    return transfer


@transaction.atomic
def cancel_transfer(transfer_id: int, user, team: Team | None) -> TransferRequest:
    transfer = _locked_transfer(transfer_id)
    if team is None or transfer.to_team_id != team.pk:
        raise PermissionDenied
    if not transfer.cancel_by_requester():
        raise TransferError('Cannot cancel this transfer request (already processed).')
    audit.info("transfer %s cancelled by user %s", transfer.pk, user.pk)
    return transfer


def request_transfer(player: Player, to_team: Team, user) -> TransferRequest:
    """Create a pending transfer request from the player's current team to ``to_team``."""
    if player.team_id == to_team.pk:
        raise TransferError('This player is already in your team.')
    try:
        transfer = TransferRequest.objects.create(
            player=player, from_team=player.team, to_team=to_team, requested_by=user,
        )
    except ValidationError as exc:
        raise TransferError(' '.join(exc.messages)) from exc
    audit.info("transfer %s requested by user %s", transfer.pk, user.pk)
    return transfer
