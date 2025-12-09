# matches/views.py - Make sure all functions exist
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Match, LeagueTable, Goal, Card
from teams.models import Zone, Team, Player
from referees.models import MatchReport

def league_tables(request):
    """Display league tables for all zones"""
    zones = Zone.objects.all()
    
    tables = {}
    for zone in zones:
        tables[zone] = LeagueTable.objects.filter(zone=zone).order_by(
            '-points', '-goal_difference', '-goals_for'
        )[:20]
    
    # Get top scorers
    top_scorers = Player.objects.filter(
        goals_scored__gt=0
    ).order_by('-goals_scored')[:10]
    
    # Get clean sheets (simplified - would need tracking)
    goalkeepers = Player.objects.filter(
        position='GK',
        matches_played__gt=0
    ).order_by('-matches_played')[:10]
    
    context = {
        'tables': tables,
        'top_scorers': top_scorers,
        'goalkeepers': goalkeepers,
        'zones': zones,
    }
    return render(request, 'matches/league_tables.html', context)

def fixtures(request):
    """Display all fixtures"""
    upcoming_matches = Match.objects.filter(
        status='scheduled'
    ).order_by('match_date')
    
    completed_matches = Match.objects.filter(
        status='completed'
    ).order_by('-match_date')[:20]
    
    zones = Zone.objects.all()
    
    context = {
        'upcoming_matches': upcoming_matches,
        'completed_matches': completed_matches,
        'zones': zones,
    }
    return render(request, 'matches/fixtures.html', context)

def match_details(request, match_id):
    """Display match details"""
    match = get_object_or_404(Match, id=match_id)
    
    # Get match report if exists
    try:
        report = MatchReport.objects.get(match=match)
    except MatchReport.DoesNotExist:
        report = None
    
    # Get goals
    goals = Goal.objects.filter(match=match).order_by('minute')
    
    # Get cards
    cards = Card.objects.filter(match=match).order_by('minute')
    
    context = {
        'match': match,
        'report': report,
        'goals': goals,
        'cards': cards,
    }
    return render(request, 'matches/match_details.html', context)

def top_scorers(request):
    """Display top scorers"""
    # Get all players with goals, ordered by goals scored
    scorers = Player.objects.filter(
        goals_scored__gt=0
    ).order_by('-goals_scored')
    
    # Group by zone
    zones = Zone.objects.all()
    scorers_by_zone = {}
    
    for zone in zones:
        scorers_by_zone[zone] = scorers.filter(team__zone=zone)[:20]
    
    context = {
        'scorers': scorers,
        'scorers_by_zone': scorers_by_zone,
        'zones': zones,
    }
    return render(request, 'matches/top_scorers.html', context)

def team_fixtures(request, team_id):
    """Display fixtures for a specific team"""
    team = get_object_or_404(Team, id=team_id)
    
    # Get all matches for this team
    matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team)
    ).order_by('match_date')
    
    # Split by status
    upcoming = matches.filter(status='scheduled')
    completed = matches.filter(status='completed')
    
    context = {
        'team': team,
        'upcoming_matches': upcoming,
        'completed_matches': completed,
    }
    return render(request, 'matches/team_fixtures.html', context)

def zone_fixtures(request, zone_id):
    """Display fixtures for a specific zone"""
    zone = get_object_or_404(Zone, id=zone_id)
    
    matches = Match.objects.filter(
        zone=zone
    ).order_by('match_date')
    
    upcoming = matches.filter(status='scheduled')
    completed = matches.filter(status='completed')
    
    context = {
        'zone': zone,
        'upcoming_matches': upcoming,
        'completed_matches': completed,
    }
    return render(request, 'matches/zone_fixtures.html', context)