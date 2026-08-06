# teams/admin_dashboard.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.db.models import Count, Q

from .models import Team, Player, Zone
from fkf_league.permissions import is_league_admin_or_manager
from fkf_league.constants import TeamStatus


def admin_or_league_manager_required(user):
    return is_league_admin_or_manager(user)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_dashboard(request):
    """Admin team/player overview — single aggregate query, no N+1."""
    stats = Team.objects.aggregate(
        total_teams    = Count('id'),
        pending_teams  = Count('id', filter=Q(status=TeamStatus.PENDING)),
        approved_teams = Count('id', filter=Q(status=TeamStatus.APPROVED)),
        paid_teams     = Count('id', filter=Q(payment_status=True)),
    )
    stats['total_players']     = Player.objects.count()
    stats['suspended_players'] = Player.objects.filter(is_suspended=True).count()
    stats['zones']             = Zone.objects.count()

    context = {
        'stats':                 stats,
        'recent_teams':          Team.objects.select_related('zone').order_by('-registration_date')[:10],
        'pending_registrations': Team.objects.filter(status=TeamStatus.PENDING)[:10],
        'suspended_players':     Player.objects.filter(is_suspended=True).select_related('team')[:10],
        'title':                 'Admin Dashboard',
    }
    return render(request, 'admin/dashboard.html', context)