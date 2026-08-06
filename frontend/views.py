# frontend/views.py
from django.shortcuts import render
from django.db.models import Count, Q

from teams.models import Team
from matches.models import Match
from fkf_league.constants import MatchStatus, TeamStatus


def home(request):
    """Homepage — stats from one aggregate, league_settings from context processor."""
    stats = Match.objects.aggregate(
        completed_matches=Count('id', filter=Q(status=MatchStatus.COMPLETED)),
    )
    return render(request, 'home.html', {
        'total_teams':       Team.objects.filter(status=TeamStatus.APPROVED).count(),
        'completed_matches': stats['completed_matches'],
        'recent_matches':    (
            Match.objects
            .filter(status=MatchStatus.COMPLETED)
            .select_related('home_team', 'away_team', 'zone')
            .order_by('-match_date')[:5]
        ),
    })


def about(request):
    return render(request, 'frontend/about.html')


def contact(request):
    return render(request, 'frontend/contact.html')


def rules(request):
    return render(request, 'frontend/rules.html')
