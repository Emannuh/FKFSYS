"""League operations: registrations, reports, suspensions, zones, windows, transfers."""
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from fkf_league.constants import MatchStatus, ReportStatus, TeamStatus, TransferStatus
from fkf_league.permissions import is_league_admin
from matches.models import LeagueTable, Suspension
from referees.models import MatchReport
from teams.models import LeagueSettings, Player, Team, TransferRequest, Zone

from .. import services
from ..activity_logger import Action, log_activity
from .common import league_admin_required


@league_admin_required
def approve_registrations(request):
    """List pending teams; POST approves (creating the manager account) or rejects."""
    if request.method == 'POST':
        team = get_object_or_404(Team, id=request.POST.get('team_id'), status=TeamStatus.PENDING)
        action = request.POST.get('action')

        if action == 'approve':
            result = services.approve_team(team)
            log_activity(request.user, Action.TEAM_APPROVE, f"Approved team {team.team_name}",
                         obj=team, request=request,
                         extra_data={'manager_id': result.manager.pk, 'manager_created': result.manager_created})
            if result.manager_created:
                messages.success(request, f"{team.team_name} approved. A manager account "
                                          f"({result.manager.username}) was created and a set-password "
                                          f"link emailed to the team contact.")
            else:
                messages.success(request, f"{team.team_name} approved and linked to manager "
                                          f"account {result.manager.username}.")
            if not team.payment_status:
                messages.warning(request, f"Payment not verified for {team.team_name}!")
        elif action == 'reject':
            team.status = TeamStatus.REJECTED
            team.save(update_fields=['status'])
            log_activity(request.user, Action.TEAM_REJECT, f"Rejected team {team.team_name}",
                         obj=team, request=request)
            messages.warning(request, f"{team.team_name} registration rejected.")
        else:
            messages.error(request, "Unknown action.")
        return redirect('admin_dashboard:approve_registrations')

    pending_teams = Team.objects.filter(status=TeamStatus.PENDING).order_by('-registration_date')
    return render(request, 'admin_dashboard/approve_registrations.html', {'pending_teams': pending_teams})


@league_admin_required
def approve_reports(request):
    """List submitted match reports; POST approves or rejects one."""
    if request.method == 'POST':
        report = get_object_or_404(
            MatchReport.objects.select_related('match'),
            id=request.POST.get('report_id'), status=ReportStatus.SUBMITTED,
        )
        action = request.POST.get('action')
        if action == 'approve':
            report.status = ReportStatus.APPROVED
            report.approved_at = timezone.now()
            report.approved_by = request.user
            report.save(update_fields=['status', 'approved_at', 'approved_by'])
            log_activity(request.user, Action.MATCH_REPORT_APPROVE, f"Approved report for {report.match}",
                         obj=report, request=request)
            messages.success(request, f"Report for {report.match} approved!")
        elif action == 'reject':
            with transaction.atomic():
                report.status = ReportStatus.REJECTED
                report.save(update_fields=['status'])
                # Re-open the match so the referee can re-submit.
                report.match.status = MatchStatus.SCHEDULED
                report.match.save(update_fields=['status'])
            log_activity(request.user, Action.MATCH_REPORT_REJECT, f"Rejected report for {report.match}",
                         obj=report, request=request)
            messages.warning(request, f"Report for {report.match} rejected.")
        else:
            messages.error(request, "Unknown action.")
        return redirect('admin_dashboard:approve_reports')

    pending_reports = (
        MatchReport.objects.filter(status=ReportStatus.SUBMITTED)
        .select_related('match__home_team', 'match__away_team', 'referee__user')
        .order_by('-submitted_at')
    )
    return render(request, 'admin_dashboard/approve_reports.html', {'pending_reports': pending_reports})


@login_required
def view_report(request, report_id):
    """A match report — league admins, or the referee who wrote it."""
    report = get_object_or_404(
        MatchReport.objects.select_related('match__home_team', 'match__away_team', 'referee__user'),
        id=report_id,
    )
    if not (is_league_admin(request.user) or report.referee.user_id == request.user.id):
        raise PermissionDenied
    return render(request, 'admin_dashboard/view_report.html', {
        'report': report,
        'title': f'Match Report #{report.id}',
    })


@league_admin_required
def view_suspensions(request):
    suspended = Player.objects.filter(is_suspended=True).select_related('team')
    context = {
        'active_suspensions': (
            Suspension.objects.filter(is_active=True)
            .select_related('player__team', 'match')
            .order_by('player__last_name')
        ),
        'red_card_players': suspended.filter(red_cards__gt=0),
        'two_yellow_players': suspended.filter(
            suspensions__is_active=True, suspensions__reason='double_yellow').distinct(),
        'yellow_card_players': suspended.filter(yellow_cards__gte=6),
    }
    return render(request, 'admin_dashboard/suspensions.html', context)


@league_admin_required
def manage_suspension(request, player_id):
    """Suspend a player for N matches, or clear all their active suspensions."""
    player = get_object_or_404(Player.objects.select_related('team'), id=player_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'suspend':
            reason = request.POST.get('reason', '').strip()
            try:
                length = int(request.POST.get('suspension_length', 1))
                services.suspend_player(player, length, reason)
            except (TypeError, ValueError) as exc:
                messages.error(request, f"Invalid suspension: {exc}")
                return redirect('admin_dashboard:manage_suspension', player_id=player.id)
            log_activity(request.user, Action.SUSPENSION_CREATE,
                         f"Suspended {player.full_name} for {length} match(es)",
                         obj=player, request=request, extra_data={'matches': length})
            messages.success(request, f"{player.full_name} suspended for {length} match(es).")
        elif action == 'clear':
            reset_cards = request.POST.get('reset_cards') == 'yes'
            closed = services.clear_suspension(player, reset_cards=reset_cards)
            log_activity(request.user, Action.SUSPENSION_LIFT, f"Cleared suspension for {player.full_name}",
                         obj=player, request=request,
                         extra_data={'suspensions_closed': closed, 'cards_reset': reset_cards})
            messages.success(request, f"{player.full_name} suspension cleared.")
        else:
            messages.error(request, "Unknown action.")
        return redirect('admin_dashboard:view_suspensions')

    return render(request, 'admin_dashboard/manage_suspension.html', {'player': player})


@league_admin_required
def statistics_dashboard(request):
    players = Player.objects.select_related('team')
    context = {
        'top_scorers': players.filter(goals_scored__gt=0).order_by('-goals_scored')[:10],
        'most_yellows': players.filter(yellow_cards__gt=0).order_by('-yellow_cards')[:10],
        'most_reds': players.filter(red_cards__gt=0).order_by('-red_cards')[:10],
        'teams_with_most_goals': (
            Team.objects.annotate(total_goals=Sum('players__goals_scored'))
            .filter(total_goals__gt=0).order_by('-total_goals')[:10]
        ),
        'zone_stats': Zone.objects.annotate(
            total_matches=Count('match'),
            completed_matches=Count('match', filter=Q(match__status=MatchStatus.COMPLETED)),
        ).order_by('name'),
    }
    return render(request, 'admin_dashboard/statistics.html', context)


@league_admin_required
def assign_zones(request):
    """Assign approved teams to zones (creating their league-table row)."""
    if request.method == 'POST':
        team = get_object_or_404(Team, id=request.POST.get('team_id'), status=TeamStatus.APPROVED)
        zone_id = request.POST.get('zone_id')
        zone = get_object_or_404(Zone, id=zone_id) if zone_id else None
        previous_zone_id = team.zone_id
        with transaction.atomic():
            team.zone = zone
            team.save(update_fields=['zone'])
            if zone:
                LeagueTable.objects.get_or_create(team=team, zone=zone)
        log_activity(request.user, Action.ZONE_ASSIGN,
                     f"Assigned {team.team_name} to {zone.name if zone else 'no zone'}",
                     obj=team, request=request,
                     extra_data={'previous_zone_id': previous_zone_id, 'zone_id': zone.pk if zone else None})
        messages.success(request, f"{team.team_name} assigned to {zone.name if zone else 'No Zone'}.")
        return redirect('admin_dashboard:assign_zones')

    zones = list(Zone.objects.order_by('name').prefetch_related(
        Prefetch('team_set', queryset=Team.objects.filter(status=TeamStatus.APPROVED), to_attr='approved_teams')
    ))
    return render(request, 'admin_dashboard/assign_zones.html', {
        'teams': Team.objects.filter(status=TeamStatus.APPROVED, zone__isnull=True).order_by('team_name'),
        'zones': zones,
        'zone_assignments': {zone: zone.approved_teams for zone in zones},
    })


# window_type -> (open flag, closed-date column, deadline column, label)
_WINDOWS = {
    'team': ('team_registration_open', 'team_registration_closed_date', 'team_registration_deadline',
             'Team registration'),
    'player': ('player_registration_open', 'player_registration_closed_date', 'player_registration_deadline',
               'Player registration'),
    'transfer': ('transfer_window_open', 'transfer_window_closed_date', 'transfer_window_deadline',
                 'Transfer window'),
}


@require_POST
@league_admin_required
def toggle_registration_window(request):
    window_type = request.POST.get('window_type')
    if window_type not in _WINDOWS:
        messages.error(request, "Unknown registration window.")
        return redirect('dashboard')
    open_field, _closed, _deadline, label = _WINDOWS[window_type]
    league_settings = LeagueSettings.get_settings()
    new_value = not getattr(league_settings, open_field)
    setattr(league_settings, open_field, new_value)
    league_settings.updated_by = request.user
    league_settings.save()
    state = 'opened' if new_value else 'closed'
    log_activity(request.user, Action.REGISTRATION_TOGGLE, f"{label} {state}",
                 request=request, extra_data={'window': window_type, 'open': new_value})
    messages.success(request, f"{label} {state}")
    return redirect('dashboard')


@require_POST
@league_admin_required
def update_registration_deadlines(request):
    """Set or clear the team/player/transfer deadlines; future deadlines re-open windows."""
    tz = timezone.get_default_timezone()
    errors = []

    def parse_deadline(field, label):
        value = request.POST.get(field, '').strip()
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            errors.append(f"Invalid {label} datetime format. Please use the picker provided.")
            return None
        return timezone.make_aware(dt, tz) if timezone.is_naive(dt) else dt.astimezone(tz)

    deadlines = {
        'team': parse_deadline('team_deadline', 'team registration'),
        'player': parse_deadline('player_deadline', 'player registration'),
        'transfer': parse_deadline('transfer_deadline', 'transfer window'),
    }
    if errors:
        messages.error(request, ' '.join(errors))
        return redirect('dashboard')

    league_settings = LeagueSettings.get_settings()
    now = timezone.now()
    for key, (open_field, closed_field, deadline_field, _label) in _WINDOWS.items():
        deadline = deadlines[key]
        if deadline and deadline > now:
            setattr(league_settings, open_field, True)
            setattr(league_settings, closed_field, None)
        setattr(league_settings, deadline_field, deadline)
    league_settings.updated_by = request.user
    league_settings.save()

    log_activity(request.user, Action.CONFIG_CHANGE, "Registration deadlines updated", request=request,
                 extra_data={k: v.isoformat() if v else None for k, v in deadlines.items()})
    messages.success(request, "Registration deadlines updated successfully.")
    return redirect('dashboard')


@league_admin_required
def manage_transfers(request):
    base = TransferRequest.objects.select_related('player', 'from_team', 'to_team')
    context = {
        'pending_transfers': base.filter(status=TransferStatus.PENDING_PARENT).select_related('requested_by'),
        'rejected_transfers': base.filter(status=TransferStatus.REJECTED).select_related('parent_decision_by'),
        'approved_transfers': base.filter(status=TransferStatus.APPROVED)[:20],
    }
    return render(request, 'admin_dashboard/transfers.html', context)


@league_admin_required
def admin_override_transfer(request, transfer_id):
    """Confirm (GET) and force-approve (POST) a pending or rejected transfer."""
    transfer = get_object_or_404(
        TransferRequest.objects.select_related('player', 'from_team', 'to_team'), id=transfer_id)

    if transfer.status not in (TransferStatus.REJECTED, TransferStatus.PENDING_PARENT):
        messages.error(request, "Only rejected or pending transfers can be approved by admin")
        return redirect('admin_dashboard:manage_transfers')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip() or 'Admin override'
        previous_status = transfer.status
        with transaction.atomic():
            transfer.override_by_admin(user=request.user, reason=reason)
        log_activity(request.user, Action.TRANSFER_OVERRIDE,
                     f"Override-approved transfer of {transfer.player.full_name} to {transfer.to_team.team_name}",
                     obj=transfer, request=request,
                     extra_data={'previous_status': previous_status, 'from_team_id': transfer.from_team_id,
                                 'to_team_id': transfer.to_team_id})
        messages.success(request, f"Transfer approved: {transfer.player.full_name} → {transfer.to_team.team_name}")
        return redirect('admin_dashboard:manage_transfers')

    return render(request, 'admin_dashboard/override_transfer.html', {'transfer': transfer})
