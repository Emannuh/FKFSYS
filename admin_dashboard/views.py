# admin_dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from teams.models import Team, Player, Zone
from payments.models import Payment
from matches.models import Match, LeagueTable
from referees.models import MatchReport, Referee

def admin_required(user):
    return user.is_staff

@login_required
@user_passes_test(admin_required)
def admin_dashboard(request):
    """Main admin dashboard"""
    # Statistics
    total_teams = Team.objects.count()
    registered_teams = Team.objects.filter(status='approved').count()
    pending_teams = Team.objects.filter(status='pending').count()
    total_players = Player.objects.count()
    total_referees = Referee.objects.count()
    
    # Payment statistics
    total_payments = Payment.objects.filter(status='completed').count()
    total_revenue = Payment.objects.filter(status='completed').aggregate(
        Sum('amount')
    )['amount__sum'] or 0
    
    # Match statistics
    total_matches = Match.objects.count()
    completed_matches = Match.objects.filter(status='completed').count()
    
    # Pending approvals
    pending_reports = MatchReport.objects.filter(status='submitted').count()
    pending_registrations = Team.objects.filter(status='pending').count()
    
    # Recent activities
    recent_payments = Payment.objects.filter(
        status='completed'
    ).order_by('-transaction_date')[:5]
    
    recent_matches = Match.objects.filter(
        status='completed'
    ).order_by('-match_date')[:5]
    
    context = {
        'total_teams': total_teams,
        'registered_teams': registered_teams,
        'pending_teams': pending_teams,
        'total_players': total_players,
        'total_referees': total_referees,
        'total_payments': total_payments,
        'total_revenue': total_revenue,
        'total_matches': total_matches,
        'completed_matches': completed_matches,
        'pending_reports': pending_reports,
        'pending_registrations': pending_registrations,
        'recent_payments': recent_payments,
        'recent_matches': recent_matches,
    }
    return render(request, 'admin_dashboard/dashboard.html', context)

@login_required
@user_passes_test(admin_required)
def approve_registrations(request):
    """Approve team registrations"""
    pending_teams = Team.objects.filter(status='pending').order_by('-registration_date')
    
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        action = request.POST.get('action')
        
        team = get_object_or_404(Team, id=team_id)
        
        if action == 'approve':
            team.status = 'approved'
            team.save()
            
            # Check if payment is made
            if not team.payment_status:
                messages.warning(request, f'{team.team_name} approved but payment not verified!')
            else:
                messages.success(request, f'{team.team_name} registration approved!')
        
        elif action == 'reject':
            team.status = 'suspended'
            team.save()
            messages.warning(request, f'{team.team_name} registration rejected.')
        
        return redirect('approve_registrations')
    
    return render(request, 'admin_dashboard/approve_registrations.html', {
        'pending_teams': pending_teams
    })

@login_required
@user_passes_test(admin_required)
def approve_reports(request):
    """Approve match reports"""
    pending_reports = MatchReport.objects.filter(
        status='submitted'
    ).order_by('-submitted_at')
    
    if request.method == 'POST':
        report_id = request.POST.get('report_id')
        action = request.POST.get('action')
        
        report = get_object_or_404(MatchReport, id=report_id)
        
        if action == 'approve':
            report.status = 'approved'
            report.approved_at = timezone.now()
            report.approved_by = request.user
            report.save()
            
            messages.success(request, f'Report for {report.match} approved!')
        
        elif action == 'reject':
            report.status = 'rejected'
            report.save()
            
            # Re-open the match for re-submission
            match = report.match
            match.status = 'scheduled'
            match.save()
            
            messages.warning(request, f'Report for {report.match} rejected.')
        
        return redirect('approve_reports')
    
    return render(request, 'admin_dashboard/approve_reports.html', {
        'pending_reports': pending_reports
    })

@login_required
@user_passes_test(admin_required)
def view_suspensions(request):
    """View suspended players"""
    # Direct red cards (3 match ban)
    red_card_players = Player.objects.filter(
        red_cards__gt=0,
        is_suspended=True
    )
    
    # Accumulated yellow cards (6 yellows = 1 match ban)
    yellow_card_players = Player.objects.filter(
        yellow_cards__gte=6,
        is_suspended=True
    )
    
    # Two yellow cards in one match (2 match ban)
    two_yellow_players = Player.objects.filter(
        yellow_cards__gte=2,
        is_suspended=True
    ).exclude(id__in=red_card_players.values('id'))
    
    context = {
        'red_card_players': red_card_players,
        'yellow_card_players': yellow_card_players,
        'two_yellow_players': two_yellow_players,
    }
    return render(request, 'admin_dashboard/suspensions.html', context)

@login_required
@user_passes_test(admin_required)
def manage_suspension(request, player_id):
    """Manage player suspension"""
    player = get_object_or_404(Player, id=player_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'suspend':
            player.is_suspended = True
            player.suspension_reason = request.POST.get('reason', '')
            
            # Set suspension end date
            suspension_length = int(request.POST.get('suspension_length', 1))
            player.suspension_end = timezone.now() + timezone.timedelta(days=7 * suspension_length)
            
            messages.success(request, f'{player.full_name} suspended for {suspension_length} match(es).')
        
        elif action == 'clear':
            player.is_suspended = False
            player.suspension_end = None
            player.suspension_reason = ''
            
            # Reset card counts if needed
            if request.POST.get('reset_cards') == 'yes':
                player.yellow_cards = 0
                player.red_cards = 0
            
            messages.success(request, f'{player.full_name} suspension cleared.')
        
        player.save()
        return redirect('view_suspensions')
    
    return render(request, 'admin_dashboard/manage_suspension.html', {
        'player': player
    })

@login_required
@user_passes_test(admin_required)
def statistics_dashboard(request):
    """Statistics and analytics dashboard"""
    # Top scorers
    top_scorers = Player.objects.filter(
        goals_scored__gt=0
    ).order_by('-goals_scored')[:10]
    
    # Most yellow cards
    most_yellows = Player.objects.filter(
        yellow_cards__gt=0
    ).order_by('-yellow_cards')[:10]
    
    # Most red cards
    most_reds = Player.objects.filter(
        red_cards__gt=0
    ).order_by('-red_cards')[:10]
    
    # Team statistics
    teams_with_most_goals = Team.objects.annotate(
        total_goals=Sum('players__goals_scored')
    ).filter(total_goals__gt=0).order_by('-total_goals')[:10]
    
    # Match statistics by zone
    zone_stats = []
    for zone in Zone.objects.all():
        matches = Match.objects.filter(zone=zone)
        completed = matches.filter(status='completed').count()
        
        zone_stats.append({
            'zone': zone,
            'total_matches': matches.count(),
            'completed_matches': completed,
            'completion_rate': (completed / matches.count() * 100) if matches.count() > 0 else 0
        })
    
    context = {
        'top_scorers': top_scorers,
        'most_yellows': most_yellows,
        'most_reds': most_reds,
        'teams_with_most_goals': teams_with_most_goals,
        'zone_stats': zone_stats,
    }
    return render(request, 'admin_dashboard/statistics.html', context)

@login_required
@user_passes_test(admin_required)
def assign_zones(request):
    """Assign teams to zones"""
    teams = Team.objects.filter(
        status='approved',
        zone__isnull=True
    ).order_by('team_name')
    
    zones = Zone.objects.all()
    
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        zone_id = request.POST.get('zone_id')
        
        team = get_object_or_404(Team, id=team_id)
        zone = get_object_or_404(Zone, id=zone_id) if zone_id else None
        
        team.zone = zone
        team.save()
        
        # Create league table entry if not exists
        if zone and not LeagueTable.objects.filter(team=team, zone=zone).exists():
            LeagueTable.objects.create(team=team, zone=zone)
        
        messages.success(request, f'{team.team_name} assigned to {zone.name if zone else "No Zone"}.')
        return redirect('assign_zones')
    
    # Get zone assignments
    zone_assignments = {}
    for zone in zones:
        zone_assignments[zone] = Team.objects.filter(zone=zone, status='approved')
    
    return render(request, 'admin_dashboard/assign_zones.html', {
        'teams': teams,
        'zones': zones,
        'zone_assignments': zone_assignments
    })