"""``/dashboard/`` role router and the super-admin overview."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render

from fkf_league.constants import MatchStatus, ReportStatus, TeamStatus, TransferStatus
from matches.models import Match
from payments.models import Payment
from referees.models import MatchReport, Referee
from teams.models import Player, Team, TransferRequest
from teams.utils import get_match_squad_data
from tournaments.models import Tournament


def _admin_overview(request):
    """Super-admin overview — aggregated counts, no per-row queries."""
    team_stats = Team.objects.aggregate(
        total=Count('id'),
        approved=Count('id', filter=Q(status=TeamStatus.APPROVED)),
        pending=Count('id', filter=Q(status=TeamStatus.PENDING)),
    )
    match_stats = Match.objects.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status=MatchStatus.COMPLETED)),
    )
    completed_payments = Payment.objects.filter(status='completed')
    payment_stats = completed_payments.aggregate(count=Count('id'), revenue=Sum('amount'))

    context = {
        'total_teams': team_stats['total'],
        'registered_teams': team_stats['approved'],
        'pending_teams': team_stats['pending'],
        'pending_registrations': team_stats['pending'],
        'total_players': Player.objects.count(),
        'total_referees': Referee.objects.count(),
        'total_payments': payment_stats['count'] or 0,
        'total_revenue': payment_stats['revenue'] or 0,
        'total_matches': match_stats['total'],
        'completed_matches': match_stats['completed'],
        'pending_reports': MatchReport.objects.filter(status=ReportStatus.SUBMITTED).count(),
        'recent_payments': completed_payments.select_related('team').order_by('-transaction_date')[:5],
        'recent_matches': (
            Match.objects.filter(status=MatchStatus.COMPLETED)
            .select_related('home_team', 'away_team', 'zone')
            .order_by('-match_date')[:5]
        ),
        'total_tournaments': Tournament.objects.count(),
        'active_suspensions': Player.objects.filter(is_suspended=True).count(),
        'pending_transfers': TransferRequest.objects.filter(status=TransferStatus.PENDING_PARENT).count(),
        'pending_referee_approvals': Referee.objects.filter(status='pending').count(),
    }
    return render(request, 'admin_dashboard/dashboard.html', context)


def _team_manager_dashboard(request):
    team = Team.objects.filter(manager=request.user).first()
    if not team:
        messages.error(request, "You are not assigned to any team.")
        return render(request, 'dashboard/default.html')
    if team.status != TeamStatus.APPROVED:
        messages.warning(request, f"Your team '{team.team_name}' is pending approval.")
        return render(request, 'dashboard/pending_approval.html', {'team': team})
    if not team.kit_colors_set:
        messages.info(request, "Please select your team kit colors first.")
        return redirect('teams:update_kits', team_id=team.id)

    current_round, matches_data = get_match_squad_data(team)
    incoming_transfers = (
        TransferRequest.objects
        .filter(from_team=team, status=TransferStatus.PENDING_PARENT)
        .select_related('player', 'to_team', 'requested_by')
        .order_by('-request_date')
    )
    context = {
        'team': team,
        'player_count': team.player_count,
        'captain_name': team.captain.full_name if team.captain else 'Not set',
        'kit_complete': team.kit_colors_set,
        'show_kit_prompt': False,
        'recent_players': team.players.order_by('-registration_date')[:10],
        'upcoming_matches': matches_data,
        'current_round': current_round,
        'incoming_transfers': incoming_transfers,
    }
    return render(request, 'dashboard/team_manager.html', context)


def _league_admin_dashboard(request):
    # league_settings comes from the context processor.
    transfer_stats = TransferRequest.objects.aggregate(
        pending=Count('id', filter=Q(status=TransferStatus.PENDING_PARENT)),
        rejected=Count('id', filter=Q(status=TransferStatus.REJECTED)),
    )
    context = {
        'pending_teams_count': Team.objects.filter(status=TeamStatus.PENDING).count(),
        # Reports awaiting admin review are SUBMITTED (drafts are still with the referee).
        'pending_reports_count': MatchReport.objects.filter(status=ReportStatus.SUBMITTED).count(),
        'pending_transfers': transfer_stats['pending'],
        'rejected_transfers': transfer_stats['rejected'],
    }
    return render(request, 'dashboard/league_manager.html', context)


@login_required
def dashboard(request):
    """Role router. Priority: superuser, Team Manager, Referees Manager,
    Referee, League Admin/staff, then a no-role fallback page."""
    user = request.user
    if user.is_superuser:
        return _admin_overview(request)

    groups = set(user.groups.values_list('name', flat=True))
    if 'Team Managers' in groups:
        return _team_manager_dashboard(request)
    if 'Referees Manager' in groups:
        return render(request, 'dashboard/referees_manager.html', {
            'pending_referees_count': Referee.objects.filter(status='pending').count(),
        })
    if 'Referee' in groups:
        return redirect('referees:referee_dashboard')
    if 'League Admin' in groups or user.is_staff:
        return _league_admin_dashboard(request)
    return render(request, 'dashboard/default.html')
