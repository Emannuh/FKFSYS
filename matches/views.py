from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.views.decorators.http import require_POST

def match_results(request):
    """Public view: List all completed match results"""
    matches = Match.objects.filter(status='completed').order_by('-match_date')
    context = {'matches': matches}
    return render(request, 'matches/match_results.html', context)

def league_admin_required(user):
    return user.is_superuser or user.groups.filter(name='League Admin').exists()

@login_required
@user_passes_test(league_admin_required)
def admin_edit_match_result(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        try:
            match.home_score = int(request.POST.get('home_score', match.home_score))
            match.away_score = int(request.POST.get('away_score', match.away_score))
            match.status = 'completed'
            match.save()
            messages.success(request, '✅ Match result updated.')
            return redirect('matches:match_results')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    context = {'match': match}
    return render(request, 'admin_dashboard/edit_match_result.html', context)

@login_required
@user_passes_test(league_admin_required)
def admin_edit_league_table(request, table_id):
    table = get_object_or_404(LeagueTable, id=table_id)
    if request.method == 'POST':
        try:
            table.matches_played = int(request.POST.get('matches_played', table.matches_played))
            table.wins = int(request.POST.get('wins', table.wins))
            table.draws = int(request.POST.get('draws', table.draws))
            table.losses = int(request.POST.get('losses', table.losses))
            table.goals_for = int(request.POST.get('goals_for', table.goals_for))
            table.goals_against = int(request.POST.get('goals_against', table.goals_against))
            table.goal_difference = int(request.POST.get('goal_difference', table.goal_difference))
            table.points = int(request.POST.get('points', table.points))
            table.save()
            messages.success(request, '✅ League table updated.')
            return redirect('matches:league_tables')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    context = {'table': table}
    return render(request, 'admin_dashboard/edit_league_table.html', context)

def league_manager_required(user):
    return user.groups.filter(name='League Manager').exists() or user.is_superuser

@login_required
@user_passes_test(league_manager_required)
def league_manager_reschedule(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if not (request.user.is_superuser or request.user.groups.filter(name='League Admin').exists()):
        messages.error(request, 'Only superusers or league admins can reschedule fixtures.')
        return redirect('matches:match_details', match_id=match_id)
    if request.method == 'POST':
        new_date = request.POST.get('new_date')
        new_kickoff_time = request.POST.get('new_kickoff_time')
        try:
            match.match_date = timezone.make_aware(datetime.strptime(new_date, '%Y-%m-%d'))
            match.kickoff_time = new_kickoff_time
            match.status = 'scheduled'
            match.save()
            messages.success(request, '✅ Match rescheduled.')
            return redirect('matches:match_details', match_id=match_id)
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    context = {'match': match}
    return render(request, 'admin_dashboard/league_manager_reschedule.html', context)
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


# --- START MATCH VIEW ---
@login_required
@user_passes_test(league_manager_required)
@require_POST
def start_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if match.status == 'live':
        messages.info(request, 'Match is already live.')
        return redirect('matches:match_details', match_id=match.id)
    match.status = 'live'
    match.start_time = timezone.now()
    match.save()
    messages.success(request, 'Match started and is now LIVE.')
    return redirect('matches:match_details', match_id=match.id)


# --- VIEW MATCH OFFICIALS VIEW ---
@login_required
def view_match_officials(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    context = {
        'match': match,
    }
    return render(request, 'matches/view_match_officials.html', context)