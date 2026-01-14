# admin_dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from django.core.mail import send_mail
from django.conf import settings
from teams.models import Team, Player, Zone, LeagueSettings, TransferRequest
from payments.models import Payment
from matches.models import Match, LeagueTable
from referees.models import MatchReport, Referee

def admin_required(user):
    """Check if user is staff (Super Admin) or in League Admin group (League Manager)"""
    return user.is_staff or user.groups.filter(name='League Admin').exists()

def superadmin_required(user):
    """Check if user is superuser - for user management only"""
    return user.is_superuser

def send_welcome_email(user, password, role):
    """
    Send welcome email to newly created user with login credentials
    """
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    
    subject = f'Welcome to FKF Meru League Management System - {role}'
    
    # Plain text version
    text_content = f"""
Dear {user.first_name} {user.last_name},

Welcome to the FKF Meru County League Management System!

Your account has been successfully created with the following details:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOGIN CREDENTIALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Username: {user.username}
Temporary Password: {password}
Role: {role}

Login URL: {settings.SITE_URL}/accounts/login/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT: CHANGE YOUR PASSWORD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For security reasons, please change your password immediately after your first login:

1. Log in using the credentials above
2. Click on your username in the top navigation bar
3. Select "Change Password" from the dropdown menu
4. Follow the prompts to set a new secure password

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECURITY TIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Create a strong password with at least 8 characters
✓ Use a mix of uppercase, lowercase, numbers, and symbols
✓ Never share your password with anyone
✓ Log out when finished using the system

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEED HELP?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If you have any questions or need assistance, please contact the system administrator.

Best regards,
FKF Meru County League Administration
    """
    
    # HTML version
    try:
        html_content = render_to_string('emails/welcome_email.html', {
            'user': user,
            'username': user.username,
            'password': password,
            'role': role,
            'login_url': f'{settings.SITE_URL}/accounts/login/'
        })
    except:
        html_content = None
    
    try:
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
        if html_content:
            email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"Error sending email to {user.email}: {str(e)}")
        return False

def send_password_reset_email(user, new_password):
    """
    Send password reset email to user
    """
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    
    subject = 'FKF Meru League - Password Reset'
    
    # Get user's role(s)
    roles = ', '.join([group.name for group in user.groups.all()])
    
    # Plain text version
    text_content = f"""
Dear {user.first_name} {user.last_name},

Your password has been reset by the system administrator.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEW LOGIN CREDENTIALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Username: {user.username}
New Password: {new_password}
Role: {roles}

Login URL: {settings.SITE_URL}/accounts/login/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT: CHANGE YOUR PASSWORD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For security reasons, please change your password immediately:

1. Log in using the new credentials above
2. Click on your username in the top navigation bar
3. Select "Change Password" from the dropdown menu
4. Follow the prompts to set a new secure password

If you did not request this password reset, please contact the system administrator immediately.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECURITY REMINDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Never share your password with anyone
✓ Use a strong, unique password
✓ Log out when finished using the system

Best regards,
FKF Meru County League Administration
    """
    
    # HTML version
    try:
        html_content = render_to_string('emails/password_reset.html', {
            'user': user,
            'username': user.username,
            'password': new_password,
            'roles': roles,
            'login_url': f'{settings.SITE_URL}/accounts/login/'
        })
    except:
        html_content = None
    
    try:
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
        if html_content:
            email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"Error sending password reset email to {user.email}: {str(e)}")
        return False

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
    PRIORITY ORDER:
    1. Super Admin (superuser) -> Full admin dashboard with user management
    2. Team Manager -> Team management dashboard
    3. Referees Manager -> Referee management dashboard
    4. Referee -> Referee portal
    5. League Manager (League Admin group) -> League operations dashboard
    6. Default -> Basic dashboard
    """
    from datetime import datetime, timedelta
    
    user = request.user
    
    # 1. SUPER ADMIN - Full access with user management
    if user.is_superuser:
        return admin_dashboard(request)  # Redirect to full admin dashboard
    
    # 2. TEAM MANAGER
    elif user.groups.filter(name='Team Managers').exists():
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
        
        # Get upcoming matches with squad info for matchday management
        from referees.models import MatchdaySquad
        today = timezone.now()
        upcoming_matches_qs = Match.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            match_date__gte=today.date(),
            status='scheduled'
        ).order_by('round_number', 'match_date', 'kickoff_time')[:5]
        
        # Find the current active round (most recent match that can be selected)
        current_round = None
        active_match = None
        
        if upcoming_matches_qs.exists():
            # Get the first upcoming match's round
            first_match = upcoming_matches_qs.first()
            current_round = first_match.round_number
            
            # Check if previous round is completed
            if current_round and current_round > 1:
                previous_round_matches = Match.objects.filter(
                    Q(home_team=team) | Q(away_team=team),
                    round_number=current_round - 1
                )
                
                # If previous round has any unplayed matches, block current round
                if previous_round_matches.filter(status='scheduled').exists():
                    current_round = None  # Block squad submission
                else:
                    active_match = first_match  # Only the first match in current round
            else:
                # First round or no round number, allow first match
                active_match = first_match
        
        # Prepare matches data with squad info
        matches_data = []
        for match in upcoming_matches_qs:
            squad = MatchdaySquad.objects.filter(match=match, team=team).first()
            
            # Determine if this match can have squad submitted
            can_submit = False
            if active_match and match.id == active_match.id:
                # Check if within submission window (4 hours before kick-off) and not after kick-off
                try:
                    if match.kickoff_time:
                        match_datetime = timezone.make_aware(
                            timezone.datetime.combine(match.match_date, match.kickoff_time)
                        )
                    else:
                        # If no kickoff time, assume noon
                        match_datetime = timezone.make_aware(
                            timezone.datetime.combine(match.match_date, timezone.datetime.strptime('12:00', '%H:%M').time())
                        )
                    time_until_match = match_datetime - today
                    # Can submit if match hasn't started yet and within 4 hours window
                    can_submit = time_until_match > timedelta(hours=0) and time_until_match <= timedelta(hours=4)
                except (ValueError, TypeError):
                    # If date/time parsing fails, allow submission
                    can_submit = True
            
            matches_data.append({
                'match': match,
                'squad': squad,
                'can_submit': can_submit,
                'is_active_match': active_match and match.id == active_match.id,
                'squad_status': squad.get_status_display() if squad else 'Not Submitted'
            })
        
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
            'upcoming_matches': matches_data,
            'current_round': current_round,
            'recent_players': Player.objects.filter(team=team).order_by('-registration_date')[:10],
            'kit_complete': team.kit_colors_set,
            'show_kit_prompt': False,
            'league_settings': settings,
            'player_registration_deadline': settings.player_registration_deadline,
            'player_registration_closed_date': settings.player_registration_closed_date,
            'transfer_window_deadline': settings.transfer_window_deadline,
            'transfer_window_closed_date': settings.transfer_window_closed_date,
            'player_registration_open': settings.player_registration_open,
            'transfer_window_open': settings.transfer_window_open,
            'incoming_transfers': incoming_transfers,
        }
        return render(request, 'dashboard/team_manager.html', context)
    
    # 3. REFEREES MANAGER
    elif user.groups.filter(name='Referees Manager').exists():
        # Get pending referees count for dashboard
        pending_referees_count = Referee.objects.filter(status='pending').count()
        
        context = {
            'pending_referees_count': pending_referees_count,
        }
        return render(request, 'dashboard/referees_manager.html', context)
    
    # 4. REFEREE
    elif user.groups.filter(name='Referee').exists():
        return redirect('referees:referee_dashboard')
    
    # 5. LEAGUE MANAGER (League Admin group) - Operations without user management
    elif user.groups.filter(name='League Admin').exists():
        # Get league settings
        settings = LeagueSettings.get_settings()
        
        # Get transfer stats
        pending_transfers = TransferRequest.objects.filter(status='pending_parent').count()
        rejected_transfers = TransferRequest.objects.filter(status='rejected').count()
        
        context = {
            'pending_teams': Team.objects.filter(status='pending'),
            'pending_reports': MatchReport.objects.filter(status='draft'),
            'league_settings': settings,
            'pending_transfers': pending_transfers,
            'rejected_transfers': rejected_transfers,
        }
        return render(request, 'dashboard/league_manager.html', context)
    
    # 6. DEFAULT DASHBOARD FOR OTHER USERS
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
            # Don't add message here - it will show on unrelated pages
        settings.team_registration_closed_date = None
    
    if player_deadline and player_deadline > now:
        if not settings.player_registration_open:
            settings.player_registration_open = True
            # Don't add message here - it will show on unrelated pages
        settings.player_registration_closed_date = None
    
    if transfer_deadline and transfer_deadline > now:
        if not settings.transfer_window_open:
            settings.transfer_window_open = True
            # Don't add message here - it will show on unrelated pages
        settings.transfer_window_closed_date = None

    settings.team_registration_deadline = team_deadline
    settings.player_registration_deadline = player_deadline
    settings.transfer_window_deadline = transfer_deadline
    settings.updated_by = request.user
    settings.save()

    messages.success(request, "Registration deadlines updated successfully.")
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
    """Super admin overrides rejection or approves pending transfers"""
    transfer = get_object_or_404(TransferRequest, id=transfer_id)
    
    if transfer.status not in ['rejected', 'pending_parent']:
        messages.error(request, "Only rejected or pending transfers can be approved by admin")
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


@login_required
@user_passes_test(superadmin_required)
def manage_league_admins(request):
    """Manage ALL users - create, view, activate/deactivate, assign roles (Super Admin Only)"""
    from django.contrib.auth.models import User, Group
    
    # Get all groups
    all_groups = Group.objects.all()
    
    # Get filter parameters
    role_filter = request.GET.get('role', 'all')
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    users = User.objects.all().prefetch_related('groups')
    
    # Apply role filter
    if role_filter != 'all':
        users = users.filter(groups__name=role_filter)
    
    # Apply status filter
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Apply search
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Order by date joined (newest first)
    users = users.distinct().order_by('-date_joined')
    
    # Get user counts by role
    user_stats = {
        'total': User.objects.count(),
        'active': User.objects.filter(is_active=True).count(),
        'inactive': User.objects.filter(is_active=False).count(),
        'team_managers': User.objects.filter(groups__name='Team Managers').count(),
        'league_admins': User.objects.filter(groups__name='League Admin').count(),
        'referees': User.objects.filter(groups__name='Referee').count(),
        'referee_managers': User.objects.filter(groups__name='Referees Manager').count(),
    }
    
    context = {
        'users': users,
        'all_groups': all_groups,
        'user_stats': user_stats,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'admin_dashboard/manage_league_admins.html', context)


@login_required
@user_passes_test(superadmin_required)
def create_league_admin(request):
    """Create a new user with selected role and send welcome email (Super Admin Only)"""
    from django.contrib.auth.models import User, Group
    from django.core.mail import send_mail
    from django.conf import settings
    import random
    import string
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role = request.POST.get('role')  # Group name
        
        # Validation
        if User.objects.filter(username=username).exists():
            messages.error(request, f"❌ Username '{username}' already exists.")
            return redirect('admin_dashboard:manage_league_admins')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, f"❌ Email '{email}' is already registered.")
            return redirect('admin_dashboard:manage_league_admins')
        
        try:
            # Generate random password
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_staff=False  # Not Django admin staff
            )
            
            # Add to selected group
            if role:
                group, _ = Group.objects.get_or_create(name=role)
                user.groups.add(group)
            
            # Send welcome email with login credentials
            send_welcome_email(user, password, role)
            
            messages.success(request, 
                f"✅ User created successfully! "
                f"Role: {role} | Username: {username} | "
                f"📧 Welcome email sent to {email} with login instructions."
            )
            
        except Exception as e:
            messages.error(request, f"❌ Error creating user: {str(e)}")
    
    return redirect('admin_dashboard:manage_league_admins')


@login_required
@user_passes_test(superadmin_required)
def toggle_league_admin_status(request, user_id):
    """Activate or deactivate a user (Super Admin Only)"""
    from django.contrib.auth.models import User
    
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deactivating yourself
    if user == request.user:
        messages.error(request, "❌ You cannot deactivate your own account!")
        return redirect('admin_dashboard:manage_league_admins')
    
    # Toggle active status
    user.is_active = not user.is_active
    user.save()
    
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f"✅ {user.username} has been {status}.")
    
    return redirect('admin_dashboard:manage_league_admins')


@login_required
@user_passes_test(superadmin_required)
def reset_league_admin_password(request, user_id):
    """Reset password for any user and send email notification (Super Admin Only)"""
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    import random
    import string
    
    user = get_object_or_404(User, id=user_id)
    
    # Generate new random password
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    user.set_password(new_password)
    user.save()
    
    # Send password reset email
    send_password_reset_email(user, new_password)
    
    messages.success(request, 
        f"✅ Password reset for {user.username}! "
        f"📧 New password sent to {user.email}."
    )
    
    return redirect('admin_dashboard:manage_league_admins')


@login_required
@user_passes_test(superadmin_required)
def edit_user_roles(request, user_id):
    """Edit user's group/role assignments (Super Admin Only)"""
    from django.contrib.auth.models import User, Group
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        # Get selected groups from form
        selected_groups = request.POST.getlist('groups')
        
        # Clear existing groups
        user.groups.clear()
        
        # Add selected groups
        for group_name in selected_groups:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
        
        messages.success(request, f"✅ Roles updated for {user.username}")
        return redirect('admin_dashboard:manage_league_admins')
    
    all_groups = Group.objects.all()
    user_groups = user.groups.all()
    
    context = {
        'edit_user': user,
        'all_groups': all_groups,
        'user_groups': user_groups,
    }
    return render(request, 'admin_dashboard/edit_user_roles.html', context)


@login_required
@user_passes_test(superadmin_required)
def delete_user(request, user_id):
    """Delete a user account (Super Admin Only)"""
    from django.contrib.auth.models import User
    
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deleting yourself
    if user == request.user:
        messages.error(request, "❌ You cannot delete your own account!")
        return redirect('admin_dashboard:manage_league_admins')
    
    # Prevent deleting superusers
    if user.is_superuser:
        messages.error(request, "❌ Cannot delete superuser accounts!")
        return redirect('admin_dashboard:manage_league_admins')
    
    username = user.username
    user.delete()
    
    messages.success(request, f"✅ User '{username}' has been deleted.")
    return redirect('admin_dashboard:manage_league_admins')