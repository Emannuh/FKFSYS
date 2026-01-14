from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from matches.models import Match
from matches.utils.fixture_generator import update_match_date
from teams.models import Team, Zone
from datetime import datetime
from django.utils import timezone

@staff_member_required
def reschedule_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        new_date = request.POST.get('new_date')
        new_kickoff_time = request.POST.get('new_kickoff_time')
        success, message = update_match_date(match.id, new_date, new_kickoff_time, new_kickoff_time)
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect(f'/matches/match/{match.id}/?updated=1')
    return render(request, 'admin_dashboard/reschedule_single.html', {'match': match})


@staff_member_required
def manage_matches(request):
    """Admin view to manage all matches"""
    # Get filter parameters
    zone_filter = request.GET.get('zone', '')
    status_filter = request.GET.get('status', '')
    round_filter = request.GET.get('round', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    matches = Match.objects.select_related('home_team', 'away_team', 'zone').all()
    
    # Apply filters
    if zone_filter:
        matches = matches.filter(zone_id=zone_filter)
    
    if status_filter:
        matches = matches.filter(status=status_filter)
    
    if round_filter:
        matches = matches.filter(round_number=round_filter)
    
    if search_query:
        matches = matches.filter(
            Q(home_team__team_name__icontains=search_query) |
            Q(away_team__team_name__icontains=search_query) |
            Q(venue__icontains=search_query)
        )
    
    # Order by date
    matches = matches.order_by('-match_date')
    
    # Get all zones and rounds for filters
    zones = Zone.objects.all()
    rounds = Match.objects.values_list('round_number', flat=True).distinct().order_by('round_number')
    
    # Count by status
    total_count = Match.objects.count()
    scheduled_count = Match.objects.filter(status='scheduled').count()
    completed_count = Match.objects.filter(status='completed').count()
    postponed_count = Match.objects.filter(status='postponed').count()
    
    context = {
        'matches': matches,
        'zones': zones,
        'rounds': rounds,
        'selected_zone': zone_filter,
        'selected_status': status_filter,
        'selected_round': round_filter,
        'search_query': search_query,
        'total_count': total_count,
        'scheduled_count': scheduled_count,
        'completed_count': completed_count,
        'postponed_count': postponed_count,
        'status_choices': Match.STATUS_CHOICES,
    }
    
    return render(request, 'admin_dashboard/manage_matches.html', context)


@staff_member_required
def create_match(request):
    """Create a new match"""
    if request.method == 'POST':
        try:
            # Get form data
            home_team_id = request.POST.get('home_team')
            away_team_id = request.POST.get('away_team')
            zone_id = request.POST.get('zone')
            match_date = request.POST.get('match_date')
            kickoff_time = request.POST.get('kickoff_time')
            venue = request.POST.get('venue')
            round_number = request.POST.get('round_number', 1)
            status = request.POST.get('status', 'scheduled')
            
            # Validate teams are different
            if home_team_id == away_team_id:
                messages.error(request, '❌ Home team and away team cannot be the same!')
                return redirect('matches:create_match')
            
            # Get teams
            home_team = Team.objects.get(id=home_team_id)
            away_team = Team.objects.get(id=away_team_id)
            zone = Zone.objects.get(id=zone_id)
            
            # Parse datetime
            match_datetime = timezone.make_aware(datetime.strptime(match_date, '%Y-%m-%d'))
            
            # Create match
            match = Match.objects.create(
                home_team=home_team,
                away_team=away_team,
                zone=zone,
                match_date=match_datetime,
                kickoff_time=kickoff_time,
                venue=venue,
                round_number=round_number,
                status=status
            )
            
            messages.success(request, f'✅ Match created successfully: {home_team.team_name} vs {away_team.team_name}')
            return redirect('matches:manage_matches')
            
        except Exception as e:
            messages.error(request, f'❌ Error creating match: {str(e)}')
            return redirect('matches:create_match')
    
    # GET request - show form
    zones = Zone.objects.all()
    teams = Team.objects.filter(status='approved').order_by('team_name')
    
    context = {
        'zones': zones,
        'teams': teams,
        'status_choices': Match.STATUS_CHOICES,
    }
    
    return render(request, 'admin_dashboard/create_match.html', context)


@staff_member_required
def edit_match(request, match_id):
    """Edit an existing match"""
    match = get_object_or_404(Match, id=match_id)
    
    if request.method == 'POST':
        try:
            # Get form data
            home_team_id = request.POST.get('home_team')
            away_team_id = request.POST.get('away_team')
            zone_id = request.POST.get('zone')
            match_date = request.POST.get('match_date')
            kickoff_time = request.POST.get('kickoff_time')
            venue = request.POST.get('venue')
            round_number = request.POST.get('round_number')
            status = request.POST.get('status')
            home_score = request.POST.get('home_score', 0)
            away_score = request.POST.get('away_score', 0)
            
            # Validate teams are different
            if home_team_id == away_team_id:
                messages.error(request, '❌ Home team and away team cannot be the same!')
                return redirect('matches:edit_match', match_id=match_id)
            
            # Update match
            match.home_team = Team.objects.get(id=home_team_id)
            match.away_team = Team.objects.get(id=away_team_id)
            match.zone = Zone.objects.get(id=zone_id)
            match.match_date = timezone.make_aware(datetime.strptime(match_date, '%Y-%m-%d'))
            match.kickoff_time = kickoff_time
            match.venue = venue
            match.round_number = round_number
            match.status = status
            match.home_score = home_score
            match.away_score = away_score
            match.save()
            
            messages.success(request, f'✅ Match updated successfully!')
            return redirect('matches:manage_matches')
            
        except Exception as e:
            messages.error(request, f'❌ Error updating match: {str(e)}')
            return redirect('matches:edit_match', match_id=match_id)
    
    # GET request - show form with existing data
    zones = Zone.objects.all()
    teams = Team.objects.filter(status='approved').order_by('team_name')
    
    context = {
        'match': match,
        'zones': zones,
        'teams': teams,
        'status_choices': Match.STATUS_CHOICES,
        'match_date_str': match.match_date.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'admin_dashboard/edit_match.html', context)


@staff_member_required
def delete_match(request, match_id):
    """Delete a match"""
    match = get_object_or_404(Match, id=match_id)
    
    if request.method == 'POST':
        match_info = f"{match.home_team.team_name} vs {match.away_team.team_name}"
        match.delete()
        messages.success(request, f'✅ Match deleted successfully: {match_info}')
        return redirect('matches:manage_matches')
    
    # GET request - show confirmation
    context = {'match': match}
    return render(request, 'admin_dashboard/delete_match.html', context)
