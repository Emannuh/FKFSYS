# matches/views.py - UPDATE YOUR FILE
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
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
    
    # Get top goalkeepers by clean sheets
    goalkeepers = Player.objects.filter(
        position='GK',
        matches_played__gt=0
    ).order_by('-clean_sheets', '-matches_played')[:10]
    
    context = {
        'tables': tables,
        'top_scorers': top_scorers,
        'goalkeepers': goalkeepers,
        'zones': zones,
    }
    return render(request, 'matches/league_tables.html', context)


def fixtures(request):
    """Display all fixtures with advanced filtering"""
    # Get filter parameters
    zone_filter = request.GET.get('zone', 'all')
    round_filter = request.GET.get('round', 'all')
    status_filter = request.GET.get('status', 'upcoming')
    date_filter = request.GET.get('date', '')
    
    # Base queryset
    matches = Match.objects.select_related(
        'home_team', 'away_team', 'zone'
    ).order_by('match_date')
    
    # Apply filters
    if zone_filter and zone_filter != 'all':
        matches = matches.filter(zone_id=zone_filter)
    
    if round_filter and round_filter != 'all':
        matches = matches.filter(round_number=round_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            matches = matches.filter(match_date__date=filter_date)
        except ValueError:
            pass
    
    # Status filter
    today = timezone.now()
    if status_filter == 'upcoming':
        matches = matches.filter(status__in=['scheduled', 'ongoing'], match_date__gte=today)
    elif status_filter == 'completed':
        matches = matches.filter(status='completed')
    elif status_filter == 'today':
        matches = matches.filter(match_date__date=today.date())
    elif status_filter == 'weekend':
        # Get this weekend (Saturday and Sunday)
        days_to_saturday = (5 - today.weekday()) % 7
        saturday = today.date() + timedelta(days=days_to_saturday)
        sunday = saturday + timedelta(days=1)
        matches = matches.filter(match_date__date__in=[saturday, sunday])
    
    # Split for display
    upcoming_matches = matches.filter(status__in=['scheduled', 'ongoing'])
    completed_matches = matches.filter(status='completed')
    
    # Get all zones for filter dropdown
    zones = Zone.objects.all()
    
    # Get unique rounds for filter dropdown
    rounds = Match.objects.values_list('round_number', flat=True).distinct().order_by('round_number')
    
    # Get counts for badges
    all_count = Match.objects.count()
    upcoming_count = Match.objects.filter(status__in=['scheduled', 'ongoing'], match_date__gte=today).count()
    completed_count = Match.objects.filter(status='completed').count()
    
    context = {
        'upcoming_matches': upcoming_matches,
        'completed_matches': completed_matches,
        'zones': zones,
        'rounds': rounds,
        'selected_zone': zone_filter,
        'selected_round': round_filter,
        'selected_status': status_filter,
        'selected_date': date_filter,
        'all_count': all_count,
        'upcoming_count': upcoming_count,
        'completed_count': completed_count,
        'today': today.date(),
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
    # Messages are handled by the view that redirects here (e.g., reschedule_match)
    # No need to add duplicate messages
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