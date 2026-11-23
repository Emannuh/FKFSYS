"""
teams/utils.py

Shared helper functions for team-related views.
Eliminates duplicated logic across dashboard, team_manager_dashboard,
and team_dashboard views.
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone


def get_match_squad_data(team, limit=5):
    """
    Build the matchday squad data structure for a team's upcoming matches.

    Eliminates the ~80-line block that was copy-pasted into:
      - admin_dashboard/views.py  (Team Manager branch of dashboard())
      - teams/views.py            (team_dashboard)
      - teams/views.py            (team_manager_dashboard)

    Returns:
        current_round   (int | None) — the active round number, or None if blocked
        matches_data    (list[dict]) — one dict per upcoming match with squad info
    """
    from referees.models import MatchdaySquad
    from matches.models import Match

    today = timezone.now()

    upcoming_qs = (
        Match.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            match_date__date__gte=timezone.localdate(),
            status='scheduled',
        )
        .select_related('home_team', 'away_team', 'zone')
        .order_by('round_number', 'match_date', 'kickoff_time')
    )[:limit]

    # ── Determine active round ───────────────────────────────────────────
    current_round = None
    active_match = None

    if upcoming_qs.exists():
        first_match = upcoming_qs.first()
        current_round = first_match.round_number

        if current_round and current_round > 1:
            prev_unplayed = Match.objects.filter(
                Q(home_team=team) | Q(away_team=team),
                round_number=current_round - 1,
                status='scheduled',
            ).exists()
            if prev_unplayed:
                current_round = None  # block submission
            else:
                active_match = first_match
        else:
            active_match = first_match  # round 1 or no round number

    # ── Build per-match data ─────────────────────────────────────────────
    matches_data = []
    for match in upcoming_qs:
        squad = MatchdaySquad.objects.filter(match=match, team=team).first()

        # Use Match.kickoff_datetime property — single source of truth
        kickoff_dt = match.kickoff_datetime
        time_until = kickoff_dt - today if kickoff_dt else None

        can_submit = bool(
            active_match
            and match.id == active_match.id
            and time_until is not None
            and timedelta(hours=0) < time_until <= timedelta(hours=4)
        )
        match_started = bool(
            time_until is not None and time_until <= timedelta(0)
        )

        matches_data.append({
            'match': match,
            'squad': squad,
            'can_submit': can_submit,
            'is_active_match': bool(active_match and match.id == active_match.id),
            'squad_status': squad.get_status_display() if squad else 'Not Submitted',
            'match_started': match_started,
        })

    return current_round, matches_data
