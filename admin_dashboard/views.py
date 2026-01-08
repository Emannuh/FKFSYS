# admin_dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from django.db.models import Sum, Count, Q
from teams.models import Team, Player, Zone, LeagueSettings, TransferRequest
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
    """Approve team registrations and create manager accounts"""
    pending_teams = Team.objects.filter(status='pending').order_by('-registration_date')
    
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        action = request.POST.get('action')
        
        team = get_object_or_404(Team, id=team_id)
        
        if action == 'approve':
            team.status = 'approved'
            team.save()
            
            # CREATE MANAGER ACCOUNT WITH DEFAULT PASSWORD
            if not team.manager:
                try:
                    from django.contrib.auth.models import User, Group
                    
                    # Generate username from email
                    base_username = team.email.split('@')[0] if '@' in team.email else team.team_name.replace(' ', '_').lower()
                    username = base_username
                    
                    # CHECK IF USER ALREADY EXISTS BY EMAIL
                    if User.objects.filter(email=team.email).exists():
                        user = User.objects.get(email=team.email)
                        created = False
                    else:
                        # Ensure username is unique by adding number suffix if needed
                        counter = 1
                        while User.objects.filter(username=username).exists():
                            username = f"{base_username}{counter}"
                            counter += 1
                        # CREATE NEW USER WITH DEFAULT PASSWORD
                        default_password = f"{team.team_code.lower()}123"
                        
                        user = User.objects.create_user(
                            username=username,
                            email=team.email,
                            password=default_password,
                            first_name=team.contact_person.split()[0] if team.contact_person else '',
                            last_name=' '.join(team.contact_person.split()[1:]) if team.contact_person and len(team.contact_person.split()) > 1 else '',
                            is_active=True
                        )
                        created = True
                    
                    # Add to Team Managers group
                    group, _ = Group.objects.get_or_create(name='Team Managers')
                    user.groups.add(group)
                    
                    # Link user to team
                    team.manager = user
                    team.save()
                    
                    if created:
                        # SHOW DEFAULT PASSWORD TO ADMIN
                        messages.success(request, 
                            f'✅ {team.team_name} approved!\n'
                            f'✅ Manager account created for: {team.contact_person}\n'
                            f'📧 Email: {team.email}\n'
                            f'🔑 Default Password: {team.team_code.lower()}123\n'
                            f'📝 Tell manager to login and change password immediately.'
                        )
                    else:
                        messages.success(request, 
                            f'✅ {team.team_name} approved!\n'
                            f'✅ Linked to existing user: {team.email}'
                        )
                        
                except Exception as e:
                    messages.error(request, f'❌ Team approved but manager account creation failed: {str(e)}')
            else:
                messages.success(request, f'✅ {team.team_name} already has a manager account.')
            
            # Check payment status
            if not team.payment_status:
                messages.warning(request, f'⚠ Payment not verified for {team.team_name}!')
        
        elif action == 'reject':
            team.status = 'rejected'
            team.save()
            messages.warning(request, f'❌ {team.team_name} registration rejected.')
        
        return redirect('admin_dashboard:approve_registrations')
    
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
        
        return redirect('admin_dashboard:approve_reports')
    
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
        return redirect('admin_dashboard:view_suspensions')
    
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
        return redirect('admin_dashboard:assign_zones')
    
    # Get zone assignments
    zone_assignments = {}
    for zone in zones:
        zone_assignments[zone] = Team.objects.filter(zone=zone, status='approved')
    
    return render(request, 'admin_dashboard/assign_zones.html', {
        'teams': teams,
        'zones': zones,
        'zone_assignments': zone_assignments
    })

@login_required
def view_report(request, report_id):
    """
    View a specific match report in detail
    """
    report = get_object_or_404(MatchReport, id=report_id)
    
    # Check permissions - only staff or the referee who submitted it can view
    if not request.user.is_staff and report.referee.user != request.user:
        messages.error(request, "You don't have permission to view this report.")
        return redirect('admin_dashboard:dashboard')
    context = {
        'report': report,
        'title': f'Match Report #{report.id}'
    }
    
    return render(request, 'admin_dashboard/view_report.html', context)


@login_required
def dashboard(request):
    """
    Main dashboard router - redirects users to appropriate dashboard based on role
    """
    from datetime import datetime, timedelta
    
    user = request.user
    
    # 1. CHECK IF USER IS TEAM MANAGER
    if user.groups.filter(name='Team Managers').exists():
        team = Team.objects.filter(manager=user).first()
        
        if not team:
            messages.error(request, "You are not assigned to any team.")
            return render(request, 'dashboard/default.html')
        
        # Check if team is approved
        if team.status != 'approved':
            messages.warning(request, f"Your team '{team.team_name}' is pending approval.")
            return render(request, 'dashboard/pending_approval.html', {'team': team})
        
        # Only force kit selection on first login; honor stored flag thereafter
        if not team.kit_colors_set:
            messages.info(request, "Please select your team kit colors first.")
            return redirect('teams:update_kits', team_id=team.id)
        
        # Get team manager dashboard data
        player_count = Player.objects.filter(team=team).count()
        
        # Get captain name
        captain = Player.objects.filter(team=team, is_captain=True).first()
        captain_name = captain.full_name if captain else "Not set"
        
        # Get upcoming matches (next 7 days)
        today = datetime.now().date()
        upcoming_matches = Match.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            match_date__gte=today,
            match_date__lte=today + timedelta(days=7)
        ).count()
        
        # Get league settings for deadlines
        settings = LeagueSettings.get_settings()
        
        # Get incoming transfer requests (other teams requesting your players)
        incoming_transfers = TransferRequest.objects.filter(
            from_team=team,
            status='pending_parent'
        ).select_related('player', 'to_team', 'requested_by').order_by('-request_date')
        
        context = {
            'team': team,
            'player_count': player_count,
            'captain_name': captain_name,
            'upcoming_matches': upcoming_matches,
            'recent_players': Player.objects.filter(team=team).order_by('-registration_date')[:10],
            'kit_complete': team.kit_colors_set,
            'show_kit_prompt': False,
            'league_settings': settings,  # Add league settings for deadlines/countdowns
            'player_registration_deadline': settings.player_registration_deadline,
            'player_registration_closed_date': settings.player_registration_closed_date,
            'transfer_window_deadline': settings.transfer_window_deadline,
            'transfer_window_closed_date': settings.transfer_window_closed_date,
            'player_registration_open': settings.player_registration_open,
            'transfer_window_open': settings.transfer_window_open,
            'incoming_transfers': incoming_transfers,  # Add incoming transfer requests
        }
        return render(request, 'dashboard/team_manager.html', context)
    
    # 2. CHECK IF USER IS REFEREES MANAGER
    elif user.groups.filter(name='Referees Manager').exists():
        if user.has_perm('referees.appoint_referees'):
            return render(request, 'dashboard/referees_manager.html')
    
    # 3. CHECK IF USER IS REFEREE
    elif user.groups.filter(name='Referee').exists():
        return redirect('referees:referee_dashboard')
    
    # 4. CHECK IF USER IS LEAGUE ADMIN OR STAFF
    elif user.groups.filter(name='League Admin').exists() or user.is_staff:
        # Get league settings
        settings = LeagueSettings.get_settings()
        
        # Get transfer stats
        pending_transfers = TransferRequest.objects.filter(status='pending_parent').count()
        rejected_transfers = TransferRequest.objects.filter(status='rejected').count()
        
        context = {
            'pending_teams': Team.objects.filter(status='pending'),
            'pending_referees': Referee.objects.filter(status='pending'),
            'pending_reports': MatchReport.objects.filter(status='draft'),
            'league_settings': settings,
            'pending_transfers': pending_transfers,
            'rejected_transfers': rejected_transfers,
        }
        return render(request, 'dashboard/league_admin.html', context)
    
    # 5. DEFAULT DASHBOARD FOR OTHER USERS
    return render(request, 'dashboard/default.html')


@login_required
@user_passes_test(admin_required)
def toggle_registration_window(request):
    """Toggle team/player/transfer registration windows"""
    if request.method == 'POST':
        settings = LeagueSettings.get_settings()
        window_type = request.POST.get('window_type')
        
        if window_type == 'team':
            settings.team_registration_open = not settings.team_registration_open
            status = "opened" if settings.team_registration_open else "closed"
            messages.success(request, f"Team registration {status}")
        elif window_type == 'player':
            settings.player_registration_open = not settings.player_registration_open
            status = "opened" if settings.player_registration_open else "closed"
            messages.success(request, f"Player registration {status}")
        elif window_type == 'transfer':
            settings.transfer_window_open = not settings.transfer_window_open
            status = "opened" if settings.transfer_window_open else "closed"
            messages.success(request, f"Transfer window {status}")
        
        settings.updated_by = request.user
        settings.save()
    
    return redirect('dashboard')


@login_required
@user_passes_test(admin_required)
def update_registration_deadlines(request):
    """Set or clear deadlines for team/player registrations and transfer window"""
    if request.method != 'POST':
        return redirect('dashboard')

    settings = LeagueSettings.get_settings()
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
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, tz)
        else:
            dt = dt.astimezone(tz)
        return dt

    team_deadline = parse_deadline('team_deadline', 'team registration')
    player_deadline = parse_deadline('player_deadline', 'player registration')
    transfer_deadline = parse_deadline('transfer_deadline', 'transfer window')

    if errors:
        messages.error(request, ' '.join(errors))
        return redirect('dashboard')
    
    now = timezone.now()

    # Auto-open windows when setting future deadlines and clear closed dates
    if team_deadline and team_deadline > now:
        if not settings.team_registration_open:
            settings.team_registration_open = True
            messages.info(request, "Team registration automatically opened due to future deadline.")
        settings.team_registration_closed_date = None
    
    if player_deadline and player_deadline > now:
        if not settings.player_registration_open:
            settings.player_registration_open = True
            messages.info(request, "Player registration automatically opened due to future deadline.")
        settings.player_registration_closed_date = None
    
    if transfer_deadline and transfer_deadline > now:
        if not settings.transfer_window_open:
            settings.transfer_window_open = True
            messages.info(request, "Transfer window automatically opened due to future deadline.")
        settings.transfer_window_closed_date = None

    settings.team_registration_deadline = team_deadline
    settings.player_registration_deadline = player_deadline
    settings.transfer_window_deadline = transfer_deadline
    settings.updated_by = request.user
    settings.save()

    messages.success(request, "Deadlines updated successfully.")
    return redirect('dashboard')


@login_required
@user_passes_test(admin_required)
def manage_transfers(request):
    """Admin view to manage all transfer requests"""
    pending = TransferRequest.objects.filter(status='pending_parent').select_related(
        'player', 'from_team', 'to_team', 'requested_by'
    )
    rejected = TransferRequest.objects.filter(status='rejected').select_related(
        'player', 'from_team', 'to_team', 'parent_decision_by'
    )
    approved = TransferRequest.objects.filter(status='approved').select_related(
        'player', 'from_team', 'to_team'
    )[:20]
    
    context = {
        'pending_transfers': pending,
        'rejected_transfers': rejected,
        'approved_transfers': approved,
    }
    return render(request, 'admin_dashboard/transfers.html', context)


@login_required
@user_passes_test(admin_required)
def admin_override_transfer(request, transfer_id):
    """Super admin overrides rejection and forces approval"""
    transfer = get_object_or_404(TransferRequest, id=transfer_id)
    
    if transfer.status != 'rejected':
        messages.error(request, "Only rejected transfers can be overridden")
        return redirect('admin_dashboard:manage_transfers')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Admin override: Approved by super admin')
        transfer.override_by_admin(user=request.user, reason=reason)
        messages.success(request, 
            f"✅ Transfer approved: {transfer.player.full_name} → {transfer.to_team.team_name}"
        )
        return redirect('admin_dashboard:manage_transfers')
    
    return render(request, 'admin_dashboard/override_transfer.html', {
        'transfer': transfer
    })