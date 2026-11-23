"""Read-only view of a team's referee-approved matchday squad."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from matches.models import Match
from referees.models import MatchdaySquad

from ..access import get_managed_team


@login_required
def view_approved_squad(request, match_id):
    team = get_managed_team(request.user)
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('teams:team_manager_dashboard')

    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team'),
        Q(home_team=team) | Q(away_team=team),
        pk=match_id,
    )
    squad = MatchdaySquad.objects.filter(match=match, team=team, status='approved').first()
    if not squad:
        messages.error(request, "No approved squad found for this match.")
        return redirect('teams:team_manager_dashboard')

    kickoff = match.kickoff_datetime
    if not kickoff:
        messages.error(request, "Match timing not set.")
        return redirect('teams:team_manager_dashboard')
    if timezone.now() < kickoff:
        messages.warning(request, "Squad details will be available after match kickoff.")
        return redirect('teams:team_manager_dashboard')

    return render(request, 'teams/view_approved_squad.html', {
        'match': match,
        'team': team,
        'squad': squad,
        'starting_players': squad.squad_players.filter(is_starting=True)
                                 .select_related('player').order_by('position_order'),
        'substitute_players': squad.squad_players.filter(is_starting=False)
                                   .select_related('player').order_by('jersey_number'),
        'completed_subs': match.substitutions.filter(team=team)
                               .select_related('player_in', 'player_out').order_by('minute'),
        'title': f'Approved Squad - {match.home_team} vs {match.away_team}',
    })
