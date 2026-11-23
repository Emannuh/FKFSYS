"""
League fixture generation (single round robin) and rescheduling helpers.

Round robin uses the circle method: one slot is fixed and the others rotate.
With an odd number of teams the fixed slot is a BYE, so every team sits out
exactly once. Home/away orientation follows the Berger pattern, which
guarantees for every team:
- home/away counts differ by at most 1 (exactly equal for odd team counts);
- never more than 2 consecutive home or away matches.
"""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from matches.models import Match
from teams.models import Team, Zone

MINIMUM_TEAMS_FOR_AUTO_FIXTURES = 4
KICKOFF_TIMES = ('13:00', '15:00', '17:00')

# Fixtures that have started or finished; regeneration must never destroy these.
PLAYED_STATUSES = (Match.Status.COMPLETED, Match.Status.LIVE, Match.Status.ONGOING)


def round_robin_pairings(teams: list) -> list[list[tuple]]:
    """
    Return rounds of (home, away) pairs for a single round robin.
    ``len(result) == n - 1`` for even n and ``n`` for odd n.
    """
    slots = list(teams)
    if len(slots) % 2:
        slots.insert(0, None)  # fixed BYE slot
    n = len(slots)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = slots[i], slots[n - 1 - i]
            if a is None or b is None:
                continue
            if i == 0:
                home_first = r % 2 == 0
            else:
                home_first = i % 2 == 1
            pairs.append((a, b) if home_first else (b, a))
        rounds.append(pairs)
        slots = [slots[0], slots[-1], *slots[1:-1]]
    return rounds


def first_match_day(zone: Zone, today: date | None = None) -> date:
    """
    Next occurrence (strictly after today) of the zone's match day.

    NOTE: ``Zone.match_day_of_week`` is interpreted as a Python weekday
    (Mon=0 .. Sun=6), which is how fixtures have always been generated.
    The labels on that field's choices in teams/models.py disagree (6 is
    labelled 'Saturday'); see the modernisation report.
    """
    today = today or timezone.localdate()
    weekday = zone.match_day_of_week if zone.match_day_of_week is not None else 6
    days_ahead = (weekday - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


def _aware(day: date, hhmm: str) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.fromisoformat(hhmm)))


def generate_fixtures_for_zone(zone_id, start_date: date | None = None, rng: random.Random | None = None):
    """
    Generate the zone's fixtures once. Returns ``(success, message)``.
    Idempotent: refuses if the zone already has generated fixtures.
    """
    rng = rng or random.Random()
    with transaction.atomic():
        zone = Zone.objects.select_for_update().filter(pk=zone_id).first()
        if zone is None:
            return False, "Zone not found"
        if zone.fixtures_generated:
            return False, f"Fixtures already generated for {zone.name}"

        teams = list(Team.objects.filter(zone=zone, status='approved').order_by('pk'))
        if len(teams) < 2:
            return False, f"Need at least 2 approved teams in zone (has {len(teams)})"
        rng.shuffle(teams)

        start = start_date or first_match_day(zone)
        matches = []
        for round_index, pairs in enumerate(round_robin_pairings(teams)):
            day = start + timedelta(weeks=round_index)
            for home, away in pairs:
                kickoff = rng.choice(KICKOFF_TIMES)
                matches.append(Match(
                    zone=zone,
                    home_team=home,
                    away_team=away,
                    round_number=round_index + 1,
                    match_date=_aware(day, kickoff),
                    kickoff_time=kickoff,
                    venue=home.home_ground or f"{home.team_name} Home Ground",
                    status=Match.Status.SCHEDULED,
                ))
        Match.objects.bulk_create(matches)

        zone.fixtures_generated = True
        zone.fixture_generation_date = timezone.now()
        zone.season_start_date = start
        zone.save(update_fields=['fixtures_generated', 'fixture_generation_date', 'season_start_date'])

    return True, f"Generated {len(matches)} fixtures for {zone.name} ({len(teams)} teams)"


def regenerate_fixtures_for_zone(zone_id):
    """
    Delete a zone's fixtures and generate them again, atomically.
    Refuses if any fixture has already been played/started, because deleting
    those would cascade-delete goals, cards and match reports.
    """
    with transaction.atomic():
        zone = Zone.objects.select_for_update().filter(pk=zone_id).first()
        if zone is None:
            return False, "Zone not found"
        played = Match.objects.filter(zone=zone, status__in=PLAYED_STATUSES).count()
        if played:
            return False, (
                f"{zone.name} has {played} played/started match(es); "
                "regeneration would delete their results. Reschedule individual matches instead."
            )
        Match.objects.filter(zone=zone).delete()
        zone.fixtures_generated = False
        zone.fixture_generation_date = None
        zone.season_start_date = None
        zone.save(update_fields=['fixtures_generated', 'fixture_generation_date', 'season_start_date'])
        return generate_fixtures_for_zone(zone.pk)


def update_match_date(match_id, new_date, new_time=None, new_kickoff_time=None):
    """
    Reschedule one match. ``new_date`` is a date or 'YYYY-MM-DD'; ``new_time``
    a time or 'HH:MM'. Without a time, the current local kickoff time is kept.
    Returns ``(success, message)``.
    """
    match = Match.objects.filter(pk=match_id).first()
    if match is None:
        return False, "Match not found"
    try:
        if isinstance(new_date, str):
            new_date = date.fromisoformat(new_date)
        if isinstance(new_time, str) and new_time:
            new_time = time.fromisoformat(new_time)
    except (TypeError, ValueError):
        return False, "Invalid date or time"
    if not isinstance(new_date, date):
        return False, "A new date is required"

    if new_time:
        match.match_date = timezone.make_aware(datetime.combine(new_date, new_time))
        match.kickoff_time = new_time.strftime('%H:%M')
    else:
        local_time = timezone.localtime(match.match_date).time()
        match.match_date = timezone.make_aware(datetime.combine(new_date, local_time))
    if new_kickoff_time:
        match.kickoff_time = str(new_kickoff_time)[:5]
    match.save(update_fields=['match_date', 'kickoff_time', 'updated_at'])
    local = timezone.localtime(match.match_date)
    kickoff = match.kickoff_time or local.strftime('%H:%M')
    return True, f"Match rescheduled to {local:%a %d %b %Y} (kickoff {kickoff})"
