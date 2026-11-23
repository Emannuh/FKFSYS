"""Business logic for league-admin actions (kept out of the views)."""
from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from fkf_league.constants import TeamStatus
from matches.models import Suspension
from teams.models import Player, Team

from .email import send_account_setup_email

User = get_user_model()

TEAM_MANAGERS_GROUP = 'Team Managers'
MAX_SUSPENSION_MATCHES = 20


@dataclass
class TeamApprovalResult:
    manager: User | None
    manager_created: bool


def _unique_username(base: str) -> str:
    base = (base or 'manager')[:140]
    username, counter = base, 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


@transaction.atomic
def approve_team(team: Team) -> TeamApprovalResult:
    """Approve a team and make sure it has a manager account.

    New manager accounts get an unusable password and an emailed single-use
    "set your password" link (sent after commit); no default password exists.
    """
    team.status = TeamStatus.APPROVED
    if team.manager_id:
        team.save(update_fields=['status'])
        return TeamApprovalResult(team.manager, False)

    manager = User.objects.filter(email__iexact=team.email).first() if team.email else None
    created = manager is None
    if created:
        base = team.email.split('@')[0] if team.email and '@' in team.email else team.team_name.replace(' ', '_').lower()
        names = (team.contact_person or '').split()
        manager = User(
            username=_unique_username(base),
            email=team.email or '',
            first_name=names[0] if names else '',
            last_name=' '.join(names[1:]),
            is_active=True,
        )
        manager.set_unusable_password()
        manager.save()
        transaction.on_commit(lambda: send_account_setup_email(manager, TEAM_MANAGERS_GROUP))

    group, _ = Group.objects.get_or_create(name=TEAM_MANAGERS_GROUP)
    manager.groups.add(group)
    team.manager = manager
    team.save(update_fields=['status', 'manager'])
    return TeamApprovalResult(manager, created)


@transaction.atomic
def suspend_player(player: Player, matches: int, reason: str) -> Suspension:
    """Create an active ``Suspension`` (which also flags the player)."""
    if not 1 <= matches <= MAX_SUSPENSION_MATCHES:
        raise ValueError(f"Suspension length must be 1–{MAX_SUSPENSION_MATCHES} matches.")
    suspension = Suspension.objects.create(
        player=player,
        reason='other',
        details=reason,
        matches_missed=matches,
        start_date=timezone.localdate(),
    )
    Player.objects.filter(pk=player.pk).update(suspension_reason=reason, suspension_matches=matches)
    return suspension


@transaction.atomic
def clear_suspension(player: Player, reset_cards: bool = False) -> int:
    """Close all active suspensions for ``player``; returns how many were closed."""
    active = list(Suspension.objects.select_for_update().filter(player=player, is_active=True))
    for suspension in active:
        suspension.is_active = False
        suspension.end_date = suspension.end_date or timezone.localdate()
        suspension.save()
    fields = {'is_suspended': False, 'suspension_end': None, 'suspension_reason': '', 'suspension_matches': 0}
    if reset_cards:
        fields.update(yellow_cards=0, red_cards=0)
    Player.objects.filter(pk=player.pk).update(**fields)
    return len(active)
