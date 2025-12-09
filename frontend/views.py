# frontend/views.py
from django.shortcuts import render
from django.db.models import Count, Sum
from teams.models import Team, Zone
from matches.models import Match
from payments.models import Payment

def home(request):
    """Homepage view"""
    # Get statistics for homepage
    total_teams = Team.objects.filter(status='approved').count()
    completed_matches = Match.objects.filter(status='completed').count()
    
    # Get recent matches
    recent_matches = Match.objects.filter(
        status='completed'
    ).order_by('-match_date')[:5]
    
    # Get league leaders
    zones = Zone.objects.all()
    
    context = {
        'total_teams': total_teams,
        'completed_matches': completed_matches,
        'recent_matches': recent_matches,
        'zones': zones,
    }
    return render(request, 'home.html', context)

def about(request):
    """About page"""
    return render(request, 'frontend/about.html')

def contact(request):
    """Contact page"""
    return render(request, 'frontend/contact.html')

def rules(request):
    """League rules page"""
    return render(request, 'frontend/rules.html')