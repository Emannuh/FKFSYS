"""
League business rules for matches: standings (league table) and round moves.

Standings are *derived* from completed matches, so recomputing is idempotent:
saving a result twice, editing a score, or deleting a match always leaves the
table consistent with the match list.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Q

from .models import LeagueTable, Match

FORM_LENGTH = 5


def compute_standing(team_id: int, zone_id: int) -> dict:
    """Stats for one team from its completed matches in one zone."""
    played = wins = draws = losses = gf = ga = 0
    form: list[str] = []
    matches = (
        Match.objects
        .filter(Q(home_team_id=team_id) | Q(away_team_id=team_id),
                zone_id=zone_id, status=Match.Status.COMPLETED)
        .order_by('-match_date', '-id')
        .only('home_team_id', 'away_team_id', 'home_score', 'away_score', 'status')
    )
    for m in matches:
        is_home = m.home_team_id == team_id
        scored, conceded = (m.home_score, m.away_score) if is_home else (m.away_score, m.home_score)
        played += 1
        gf += scored
        ga += conceded
        if scored > conceded:
            wins += 1
            result = 'W'
        elif scored < conceded:
            losses += 1
            result = 'L'
        else:
            draws += 1
            result = 'D'
        if len(form) < FORM_LENGTH:
            form.append(result)  # most recent first
    return {
        'matches_played': played, 'wins': wins, 'draws': draws, 'losses': losses,
        'goals_for': gf, 'goals_against': ga, 'form': ''.join(form),
    }


def recalculate_standing(team_id: int, zone_id: int) -> LeagueTable:
    stats = compute_standing(team_id, zone_id)
    with transaction.atomic():
        row, _ = LeagueTable.objects.select_for_update().get_or_create(team_id=team_id, zone_id=zone_id)
        for field, value in stats.items():
            setattr(row, field, value)
        row.save()  # derives goal_difference + points
    return row


def recalculate_for_match(match: Match) -> None:
    """Refresh both teams' rows for the match's zone."""
    if not (match.zone_id and match.home_team_id and match.away_team_id):
        return
    for team_id in (match.home_team_id, match.away_team_id):
        recalculate_standing(team_id, match.zone_id)


def recalculate_zone(zone_id: int) -> None:
    """Rebuild every existing row of a zone (e.g. after manual data fixes)."""
    team_ids = set(LeagueTable.objects.filter(zone_id=zone_id).values_list('team_id', flat=True))
    for home, away in Match.objects.filter(zone_id=zone_id).values_list('home_team_id', 'away_team_id'):
        team_ids.update((home, away))
    for team_id in team_ids:
        recalculate_standing(team_id, zone_id)


def move_match_to_round(match: Match, new_round: int) -> Match | None:
    """
    Move ``match`` to ``new_round``. If another match of the same zone already
    occupies that round, it is swapped into the old round. Returns the swapped
    match (or None). Atomic.
    """
    old_round = match.round_number
    if old_round == new_round:
        return None
    with transaction.atomic():
        swap = (
            Match.objects.select_for_update()
            .filter(zone_id=match.zone_id, round_number=new_round)
            .exclude(pk=match.pk)
            .first()
        )
        if swap:
            Match.objects.filter(pk=swap.pk).update(round_number=old_round)
        Match.objects.filter(pk=match.pk).update(round_number=new_round)
    match.round_number = new_round
    return swap
