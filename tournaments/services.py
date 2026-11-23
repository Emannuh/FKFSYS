"""Tournament business rules: fixture generation, standings, knockout
progression and matchday squads.

Views call these functions; they hold no request handling.
"""
from __future__ import annotations

import logging
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TypeVar

from django.db import transaction
from django.utils import timezone

from .models import (
    ExternalPlayer,
    Tournament,
    TournamentGroup,
    TournamentGroupStanding,
    TournamentMatch,
    TournamentMatchdaySquad,
    TournamentSquadPlayer,
    TournamentTeamRegistration,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')

POINTS_FOR_WIN = 3
POINTS_FOR_DRAW = 1

MAX_KNOCKOUT_BRACKET = 32
# Number of matches in a knockout round -> stage code.
KNOCKOUT_STAGE_BY_MATCHES = {
    1: 'final',
    2: 'semi_final',
    4: 'quarter_final',
    8: 'round_of_16',
    16: 'round_of_32',
}
# Rounds in bracket order; used to find the round after a given stage.
KNOCKOUT_STAGE_ORDER = ['round_of_32', 'round_of_16', 'quarter_final', 'semi_final', 'final']

MIN_STARTING = 7
MAX_STARTING = 11
MAX_SUBSTITUTES = 14


class FixtureGenerationError(Exception):
    """Fixture generation cannot proceed (message is user-facing)."""


# ---------------------------------------------------------------------------
#  Pairing algorithms (pure functions, no database)
# ---------------------------------------------------------------------------
def round_robin_rounds(teams: Sequence[T]) -> list[list[tuple[T, T]]]:
    """Single round-robin schedule using the circle method.

    Returns ``n - 1`` rounds (``n`` rounded up to even). With an odd number of
    teams one team sits out each round. Every pair meets exactly once.
    """
    slots: list[T | None] = list(teams)
    if len(slots) % 2:
        slots.append(None)
    n = len(slots)
    rounds: list[list[tuple[T, T]]] = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = slots[i], slots[n - 1 - i]
            if a is None or b is None:
                continue
            # The fixed first slot would otherwise always be at home.
            if i == 0 and r % 2:
                a, b = b, a
            pairs.append((a, b))
        rounds.append(pairs)
        slots = [slots[0], slots[-1], *slots[1:-1]]
    return rounds


def next_power_of_two(n: int) -> int:
    size = 1
    while size < n:
        size *= 2
    return size


def knockout_stage_for(matches_in_round: int) -> str:
    try:
        return KNOCKOUT_STAGE_BY_MATCHES[matches_in_round]
    except KeyError:
        raise FixtureGenerationError(
            f'Knockout brackets larger than {MAX_KNOCKOUT_BRACKET} teams are not supported.'
        ) from None


def order_for_draw(regs: Sequence[TournamentTeamRegistration]) -> list[TournamentTeamRegistration]:
    """Seeded teams first (by seed), then the rest in random order."""
    seeded = sorted((r for r in regs if r.seed is not None), key=lambda r: r.seed)
    unseeded = [r for r in regs if r.seed is None]
    random.shuffle(unseeded)
    return seeded + unseeded


# ---------------------------------------------------------------------------
#  Fixture generation
# ---------------------------------------------------------------------------
@dataclass
class _Schedule:
    tournament: Tournament
    first_date: datetime
    interval_days: int
    venue: str
    match_number: int = 0

    def date_for_round(self, round_index: int) -> datetime:
        return self.first_date + timedelta(days=self.interval_days * round_index)

    def create(self, **fields) -> TournamentMatch:
        self.match_number += 1
        return TournamentMatch.objects.create(
            tournament=self.tournament,
            match_number=self.match_number,
            venue=self.venue,
            **fields,
        )


def _create_group(tournament, name, regs) -> TournamentGroup:
    group = TournamentGroup.objects.create(tournament=tournament, name=name)
    group.teams.set(regs)
    TournamentGroupStanding.objects.bulk_create(
        TournamentGroupStanding(group=group, team_registration=r) for r in regs
    )
    return group


def _schedule_group(schedule: _Schedule, group: TournamentGroup, regs) -> int:
    """Create the round-robin matches of one group. Returns rounds used."""
    rounds = round_robin_rounds(regs)
    for r, pairs in enumerate(rounds):
        for home, away in pairs:
            schedule.create(
                group=group, stage='group', home_team=home, away_team=away,
                match_date=schedule.date_for_round(r),
            )
    return len(rounds)


def _schedule_knockout_bracket(schedule: _Schedule, bracket_size: int, first_round: int,
                               entrants: Sequence[TournamentTeamRegistration] = ()):
    """Create every round of a knockout bracket of ``bracket_size`` slots.

    ``entrants`` (may be empty for placeholder brackets) fill the first round.
    When there are fewer entrants than slots, the first ``byes`` entrants skip
    the first round and are placed straight into the second round. Bye slots
    sit at the end of the first round so match numbers stay positional
    (see :func:`advance_knockout_winner`).
    """
    rounds: list[list[TournamentMatch | None]] = []
    matches_in_round = bracket_size // 2
    byes = bracket_size - len(entrants) if entrants else 0
    real_first_round = matches_in_round - byes
    round_index = first_round
    while matches_in_round >= 1:
        stage = knockout_stage_for(matches_in_round)
        date = schedule.date_for_round(round_index)
        this_round: list[TournamentMatch | None] = []
        for slot in range(matches_in_round):
            if not rounds and entrants and slot >= real_first_round:
                schedule.match_number += 1  # keep numbering positional for byes
                this_round.append(None)
                continue
            fields = {}
            if not rounds and entrants:
                fields = {
                    'home_team': entrants[byes + 2 * slot],
                    'away_team': entrants[byes + 2 * slot + 1],
                }
            this_round.append(schedule.create(stage=stage, match_date=date, **fields))
        rounds.append(this_round)
        matches_in_round //= 2
        round_index += 1

    # Place bye teams directly into round two.
    if byes and len(rounds) > 1:
        for k, reg in enumerate(entrants[:byes]):
            slot = real_first_round + k
            target = rounds[1][slot // 2]
            setattr(target, 'home_team' if slot % 2 == 0 else 'away_team', reg)
        for target in rounds[1]:
            target.save(update_fields=['home_team', 'away_team', 'updated_at'])


def _generate_knockout(schedule: _Schedule, regs):
    entrants = order_for_draw(regs)
    bracket = next_power_of_two(len(entrants))
    if bracket > MAX_KNOCKOUT_BRACKET:
        knockout_stage_for(bracket // 2)  # raises
    _schedule_knockout_bracket(schedule, bracket, first_round=0, entrants=entrants)


def _generate_round_robin(schedule: _Schedule, regs):
    entrants = order_for_draw(regs)
    group = _create_group(schedule.tournament, 'League Table', entrants)
    _schedule_group(schedule, group, entrants)


def _generate_group_knockout(schedule: _Schedule, regs):
    entrants = order_for_draw(regs)
    # Every group needs at least two teams.
    group_count = max(1, min(schedule.tournament.group_count or 1, len(entrants) // 2))
    buckets: list[list[TournamentTeamRegistration]] = [[] for _ in range(group_count)]
    for i, reg in enumerate(entrants):
        buckets[i % group_count].append(reg)

    rounds_used = 0
    for g, bucket in enumerate(buckets):
        group = _create_group(schedule.tournament, f'Group {chr(65 + g)}', bucket)
        rounds_used = max(rounds_used, _schedule_group(schedule, group, bucket))

    # Top two from each group qualify; knockout slots are filled later.
    bracket = next_power_of_two(group_count * 2)
    _schedule_knockout_bracket(schedule, bracket, first_round=rounds_used)


GENERATORS = {
    'knockout': _generate_knockout,
    'group_knockout': _generate_group_knockout,
    'round_robin': _generate_round_robin,
    # Swiss pairing is not implemented; it is scheduled as a round robin.
    'swiss': _generate_round_robin,
}


def generate_fixtures(tournament: Tournament, *, first_date: datetime, interval_days: int,
                      venue: str = '', user=None) -> int:
    """(Re)generate all fixtures for ``tournament``. Returns matches created.

    Runs in one transaction: existing matches and groups are deleted and the
    schedule rebuilt, so running it twice leaves one schedule, never two.
    """
    regs = list(
        tournament.registrations.filter(status='approved')
        .select_related('team', 'external_team')
    )
    if len(regs) < 2:
        raise FixtureGenerationError('Need at least 2 approved teams to generate fixtures.')

    generator = GENERATORS.get(tournament.format, _generate_round_robin)
    schedule = _Schedule(tournament, first_date, interval_days, venue or tournament.venue)
    with transaction.atomic():
        removed = tournament.matches.count()
        tournament.matches.all().delete()
        tournament.groups.all().delete()
        generator(schedule, regs)
        created = tournament.matches.count()
    logger.info(
        'Fixtures generated: tournament=%s user=%s removed=%d created=%d',
        tournament.pk, getattr(user, 'pk', None), removed, created,
    )
    return created


# ---------------------------------------------------------------------------
#  Results: standings and knockout progression
# ---------------------------------------------------------------------------
def standing_sort_key(standing: TournamentGroupStanding) -> tuple:
    """Points, then goal difference, then goals scored (all descending)."""
    return (-standing.points, -standing.goal_difference, -standing.goals_for)


def recompute_group_standings(group: TournamentGroup) -> None:
    """Rebuild every standing row in ``group`` from its completed matches.

    Idempotent: recording or correcting a result never double-counts.
    """
    rows = {s.team_registration_id: s for s in group.standings.all()}
    for row in rows.values():
        row.played = row.won = row.drawn = row.lost = 0
        row.goals_for = row.goals_against = 0

    matches = group.matches.filter(
        status='completed', home_team__isnull=False, away_team__isnull=False,
    )
    for m in matches:
        for reg_id, scored, conceded in (
            (m.home_team_id, m.home_score, m.away_score),
            (m.away_team_id, m.away_score, m.home_score),
        ):
            row = rows.get(reg_id)
            if row is None:
                row = rows[reg_id] = TournamentGroupStanding.objects.create(
                    group=group, team_registration_id=reg_id,
                )
            row.played += 1
            row.goals_for += scored
            row.goals_against += conceded
            if scored > conceded:
                row.won += 1
            elif scored == conceded:
                row.drawn += 1
            else:
                row.lost += 1

    TournamentGroupStanding.objects.bulk_update(
        rows.values(),
        ['played', 'won', 'drawn', 'lost', 'goals_for', 'goals_against'],
    )


def advance_knockout_winner(match: TournamentMatch) -> TournamentMatch | None:
    """Put the winner of a completed knockout match into the next round.

    Matches in a round are positional by ``match_number``: the i-th match of a
    round feeds slot ``i % 2`` (home/away) of match ``i // 2`` of the next
    round. Returns the updated next-round match, or None.
    """
    winner = match.winner
    if winner is None or match.stage not in KNOCKOUT_STAGE_ORDER or match.stage == 'final':
        return None
    next_stage = KNOCKOUT_STAGE_ORDER[KNOCKOUT_STAGE_ORDER.index(match.stage) + 1]
    tournament_matches = TournamentMatch.objects.filter(tournament_id=match.tournament_id)
    first_number = (
        tournament_matches.filter(stage=match.stage).order_by('match_number')
        .values_list('match_number', flat=True).first()
    )
    position = match.match_number - first_number
    next_round = list(tournament_matches.filter(stage=next_stage).order_by('match_number'))
    if position // 2 >= len(next_round):
        return None
    target = next_round[position // 2]
    if target.status == 'completed':
        return None
    setattr(target, 'home_team' if position % 2 == 0 else 'away_team', winner)
    target.save(update_fields=['home_team', 'away_team', 'updated_at'])
    return target


def record_match_result(match: TournamentMatch) -> None:
    """Persist a completed result and update standings / bracket."""
    with transaction.atomic():
        match.status = 'completed'
        match.save()
        if match.group_id:
            recompute_group_standings(match.group)
        else:
            advance_knockout_winner(match)


# ---------------------------------------------------------------------------
#  Matchday squads
# ---------------------------------------------------------------------------
def eligible_squad_players(reg: TournamentTeamRegistration):
    """Players a team may name in a matchday squad (ordered for display)."""
    if reg.team_type == 'league' and reg.team_id:
        return reg.team.players.filter(is_suspended=False).order_by('position', 'jersey_number')
    if reg.team_type == 'external' and reg.external_team_id:
        return reg.external_team.players.order_by('position', 'jersey_number')
    return ExternalPlayer.objects.none()


def player_field_for(reg: TournamentTeamRegistration) -> str:
    return 'player' if reg.team_type == 'league' else 'external_player'


def _parse_ids(raw: Sequence[str]) -> list[int] | None:
    try:
        ids = [int(x) for x in raw]
    except (TypeError, ValueError):
        return None
    return ids if len(ids) == len(set(ids)) else None


def submit_matchday_squad(squad: TournamentMatchdaySquad, starting_raw: Sequence[str],
                          subs_raw: Sequence[str], user) -> list[str]:
    """Validate and save a squad. Returns a list of errors (empty on success)."""
    starting, subs = _parse_ids(starting_raw), _parse_ids(subs_raw)
    if starting is None or subs is None:
        return ['Invalid player selection.']
    if len(starting) < MIN_STARTING:
        return [f'Select at least {MIN_STARTING} starting players. You selected {len(starting)}.']
    if len(starting) > MAX_STARTING:
        return [f'Max {MAX_STARTING} starting players. You selected {len(starting)}.']
    if len(subs) > MAX_SUBSTITUTES:
        return [f'Max {MAX_SUBSTITUTES} substitutes. You selected {len(subs)}.']
    if set(starting) & set(subs):
        return ['A player cannot be in both starting and substitutes.']

    eligible = {p.pk: p for p in eligible_squad_players(squad.team_registration)}
    if not set(starting + subs) <= eligible.keys():
        return ['One or more selected players are not eligible for this team.']
    if not any(eligible[pk].position == 'GK' for pk in starting):
        return ['The starting line-up must include at least one goalkeeper.']

    field = player_field_for(squad.team_registration)
    with transaction.atomic():
        squad.status = 'submitted'
        squad.submitted_by = user
        squad.submitted_at = timezone.now()
        squad.save()
        squad.squad_players.all().delete()
        entries = [
            TournamentSquadPlayer(
                squad=squad, is_starting=True, position_order=i,
                jersey_number=eligible[pk].jersey_number, **{field: eligible[pk]},
            )
            for i, pk in enumerate(starting)
        ] + [
            TournamentSquadPlayer(
                squad=squad, is_starting=False,
                jersey_number=eligible[pk].jersey_number, **{field: eligible[pk]},
            )
            for pk in subs
        ]
        TournamentSquadPlayer.objects.bulk_create(entries)
    return []
