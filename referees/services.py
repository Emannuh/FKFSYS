"""
Business logic shared by the referees views (and the signal handlers).

Keep views thin: anything that changes several rows, sends notifications or
encodes a league rule lives here.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import MatchdaySquad, MatchOfficials, Referee, ReservePlayer, StartingLineup

logger = logging.getLogger(__name__)

REFEREE_GROUP = 'Referee'


# ---------------------------------------------------------------- accounts
def approve_referee(referee: Referee, approved_by, request) -> tuple[bool, bool]:
    """
    Approve a referee, add them to the Referee group and email a set-password link.

    No password is ever generated, displayed or emailed. Returns
    ``(group_found, email_sent)`` so the caller can warn the approver.
    """
    with transaction.atomic():
        referee.approve(approved_by)
        group = Group.objects.filter(name=REFEREE_GROUP).first()
        if group:
            referee.user.groups.add(group)
    return group is not None, send_account_setup_email(referee, request)


def send_account_setup_email(referee: Referee, request) -> bool:
    user = referee.user
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    setup_url = request.build_absolute_uri(
        reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
    )
    body = render_to_string('referees/emails/account_setup.txt', {
        'referee': referee,
        'username': user.username,
        'setup_url': setup_url,
        'login_url': request.build_absolute_uri(reverse('login')),
    })
    try:
        send_mail(
            'Your FKF Meru referee account has been approved',
            body, settings.DEFAULT_FROM_EMAIL, [referee.email],
        )
    except Exception:  # noqa: BLE001 - mail outages must not block approval
        logger.exception("Account set-up email failed for referee id=%s", referee.pk)
        return False
    return True


# ------------------------------------------------------------ appointments
def notify_appointment_cancelled(match, appointed: list[tuple[str, Referee]]) -> int:
    """Email every previously appointed official. Returns the number notified."""
    sent = 0
    for role_label, referee in appointed:
        if not referee.email:
            continue
        body = render_to_string('referees/emails/appointment_cancelled.txt', {
            'referee': referee, 'match': match, 'role': role_label,
        })
        try:
            send_mail(
                f'Match Appointment Cancelled - {match.home_team} vs {match.away_team}',
                body, settings.DEFAULT_FROM_EMAIL, [referee.email],
            )
            sent += 1
        except Exception:  # noqa: BLE001
            logger.exception("Cancellation email failed for referee id=%s", referee.pk)
    return sent


def appointments_for(referee: Referee):
    """MatchOfficials rows in which ``referee`` holds any role."""
    from django.db.models import Q
    q = Q()
    for field in ('main_referee', 'assistant_1', 'assistant_2', 'fourth_official',
                  'reserve_referee', 'reserve_assistant', 'var', 'avar1', 'avar2',
                  'match_commissioner'):
        q |= Q(**{field: referee})
    return MatchOfficials.objects.filter(q)


def is_appointed_to(referee: Referee | None, match) -> bool:
    officials = getattr(match, 'officials', None) if match else None
    if referee is None:
        return False
    if match.referee_id == referee.pk:
        return True
    return bool(officials and officials.role_of(referee))


def is_centre_referee(referee: Referee | None, match) -> bool:
    if referee is None:
        return False
    if match.referee_id == referee.pk:
        return True
    officials = getattr(match, 'officials', None)
    return bool(officials and officials.main_referee_id == referee.pk)


# ------------------------------------------------------------ results
def record_result(match, home_score: int, away_score: int) -> None:
    """
    Set the full-time score and mark the match completed via a normal ``save()``
    so Match post_save signals run (clean sheets here; on the matches branch the
    league table is derived from results by matches.services.recalculate_for_match).
    No hand-rolled league-table increments: those double-counted on resubmission.
    """
    match.home_score = home_score
    match.away_score = away_score
    match.status = 'completed'
    match.save()


# --------------------------------------------------------- matchday squads
def populate_lineup_from_squad(squad: MatchdaySquad) -> None:
    """Replace the match-report lineup/reserves for ``squad.team`` with the squad."""
    match = squad.match
    StartingLineup.objects.filter(match=match, team=squad.team).delete()
    ReservePlayer.objects.filter(match=match, team=squad.team).delete()
    players = list(squad.squad_players.select_related('player'))
    StartingLineup.objects.bulk_create([
        StartingLineup(
            match=match, team=squad.team, player=sp.player,
            jersey_number=sp.player.jersey_number,
            position=sp.player.get_position_display(),
        )
        for sp in players if sp.is_starting
    ])
    ReservePlayer.objects.bulk_create([
        ReservePlayer(
            match=match, team=squad.team, player=sp.player,
            jersey_number=sp.player.jersey_number,
        )
        for sp in players if not sp.is_starting
    ])


def approve_squad(squad: MatchdaySquad, referee: Referee) -> bool:
    """Approve a submitted squad and copy it into the match report. Idempotent."""
    if squad.status != MatchdaySquad.Status.SUBMITTED:
        return False
    now = timezone.now()
    with transaction.atomic():
        squad.squad_players.update(is_approved=True, approved_at=now)
        squad.status = MatchdaySquad.Status.APPROVED
        squad.approved_at = now
        squad.approved_by = referee
        squad.save()
        populate_lineup_from_squad(squad)
    return True
