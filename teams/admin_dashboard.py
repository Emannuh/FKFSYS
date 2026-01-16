# teams/admin_dashboard.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from .models import Team, Player, Zone

def admin_or_league_manager_required(user):
    """Check if user is staff or in League Admin or League Manager group"""
    return user.is_staff or user.groups.filter(name__in=['League Admin', 'League Manager']).exists()

@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_dashboard(request):
    # Collect statistics
    stats = {
        'total_teams': Team.objects.count(),
        'pending_teams': Team.objects.filter(status='pending').count(),
        'approved_teams': Team.objects.filter(status='approved').count(),
        'paid_teams': Team.objects.filter(payment_status=True).count(),
        'total_players': Player.objects.count(),
        'suspended_players': Player.objects.filter(is_suspended=True).count(),
        'zones': Zone.objects.count(),
    }
    
    # Get recent data
    recent_teams = Team.objects.order_by('-registration_date')[:10]  # Last 10 teams
    pending_registrations = Team.objects.filter(status='pending')[:10]
    suspended_players = Player.objects.filter(is_suspended=True)[:10]
    
    # Prepare data to send to template
    context = {
        'stats': stats,
        'recent_teams': recent_teams,
        'pending_registrations': pending_registrations,
        'suspended_players': suspended_players,
        'title': 'Admin Dashboard',
    }
    
    # Render the dashboard page
    return render(request, 'admin/dashboard.html', context)