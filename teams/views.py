from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Team, Player, Zone, LeagueSettings, TransferRequest, TeamOfficial
from .forms import TeamRegistrationForm, PlayerRegistrationForm, TeamKitForm
from .officials_forms import TeamOfficialForm
from payments.models import Payment

def team_registration(request):
    # Check if team registration is open
    settings = LeagueSettings.get_settings()
    if not settings.team_registration_open:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Team Registration Closed',
            'message': 'Team registration is currently closed. Please check back later or contact the league administrator for more information.',
            'deadline': settings.team_registration_deadline
        })
    
    if request.method == 'POST':
        form = TeamRegistrationForm(request.POST, request.FILES)
        print(f"Form is valid: {form.is_valid()}")  # Debug
        if form.is_valid():
            try:
                team = form.save(commit=False)
                team.status = 'pending'
                
                # Generate team code if not already set in model save method
                if not team.team_code:
                    import uuid
                    team.team_code = str(uuid.uuid4())[:8].upper()
                
                team.save()
                print(f"Team saved: {team.team_name}, Code: {team.team_code}")  # Debug
                
                # Store in session for success page - NOT for add_players
                request.session['registration_success'] = True
                request.session['success_team_name'] = team.team_name
                request.session['success_team_code'] = team.team_code
                
                # Add success message
                messages.success(request, 
                    f'✅ Team "{team.team_name}" registered successfully! '
                    f'Your Team Code: <strong>{team.team_code}</strong>'
                )
                
                # REDIRECT to registration_success page
                return redirect('teams:registration_success')
                
            except Exception as e:
                print(f"Error saving team: {e}")  # Debug
                messages.error(request, f'Error saving team: {str(e)}')
        else:
            print(f"Form errors: {form.errors}")  # Debug
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"{error}")
                    else:
                        messages.error(request, f"{field}: {error}")
    
    else:
        form = TeamRegistrationForm()
    
    return render(request, 'teams/register.html', {'form': form})
def add_players(request):
    """Add players to team - Only accessible after approval"""
    # Check session for registration
    team_id = request.session.get('team_id')
    
    if not team_id:
        messages.error(request, 'Please register a team first!')
        return redirect('teams:team_registration')
    
    team = get_object_or_404(Team, id=team_id)
    
    # If user is logged in and this is not their team, check approval
    if request.user.is_authenticated and team.manager != request.user:
        if team.status != 'approved':
            messages.error(request, 'Your team is pending approval. You cannot add players yet.')
            return redirect('frontend:home')
    
    if request.method == 'POST':
        form = PlayerRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            player = form.save(commit=False)
            player.team = team
            
            # Check jersey number uniqueness
            if Player.objects.filter(team=team, jersey_number=player.jersey_number).exists():
                messages.error(request, f'Jersey number {player.jersey_number} is already taken.')
            else:
                # Check if ID number already exists
                if Player.objects.filter(id_number=player.id_number).exists():
                    messages.error(request, f'ID Number {player.id_number} is already registered.')
                else:
                    player.save()
                    messages.success(request, f'✅ Player {player.full_name} added successfully!')
                    
                    # FIXED: Check for 'action' parameter instead of button names
                    action = request.POST.get('action', 'add_more')
                    
                    if action == 'finish':
                        # Store team data in session BEFORE clearing
                        team_name = team.team_name
                        team_code = team.team_code
                        
                        # Clear session
                        if 'team_id' in request.session:
                            del request.session['team_id']
                        if 'team_code' in request.session:
                            del request.session['team_code']
                        
                        # Store in session for success page
                        request.session['registration_success'] = True
                        request.session['success_team_name'] = team_name
                        request.session['success_team_code'] = team_code
                        
                        # Add final success message
                        messages.success(request, 
                            f'🎉 REGISTRATION COMPLETE!<br>'
                            f'<strong>Team:</strong> {team_name}<br>'
                            f'<strong>Team Code:</strong> {team_code}<br>'
                            f'<strong>Status:</strong> Pending Approval<br>'
                            f'Admin will review and approve your registration.'
                        )
                        
                        return redirect('teams:registration_success')
                    else:
                        # Reset form for adding another player
                        form = PlayerRegistrationForm()
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PlayerRegistrationForm()
    
    players = Player.objects.filter(team=team).order_by('jersey_number')
    player_count = players.count()
    
    return render(request, 'teams/add_players.html', {
        'form': form,
        'team': team,
        'players': players,
        'player_count': player_count
    })

def registration_success(request):
    # Get data from session
    success = request.session.get('registration_success', False)
    team_name = request.session.get('success_team_name', '')
    team_code = request.session.get('success_team_code', '')
    
    # Clear session data
    if 'registration_success' in request.session:
        del request.session['registration_success']
    if 'success_team_name' in request.session:
        del request.session['success_team_name']
    if 'success_team_code' in request.session:
        del request.session['success_team_code']
    
    # If no success data, redirect to registration
    if not success:
        messages.info(request, 'Please complete team registration first.')
        return redirect('teams:team_registration')
    
    return render(request, 'teams/registration_success.html', {
        'team_name': team_name,
        'team_code': team_code,
        'success': success
    })

def team_dashboard(request, team_id=None):
    # If team_id is provided, show that team's dashboard
    if team_id:
        team = get_object_or_404(Team, id=team_id)
    # If user is team manager, show their team's dashboard
    elif request.user.is_authenticated and hasattr(request.user, 'managed_teams'):
        team = request.user.managed_teams.first()
        if not team:
            messages.error(request, "You are not assigned to any team.")
            return redirect('dashboard')
    else:
        messages.error(request, "Please specify a team.")
        return redirect('teams:all_teams')
    
    players = Player.objects.filter(team=team).order_by('jersey_number')
    payments = Payment.objects.filter(team=team) if hasattr(Payment, 'objects') else []
    
    return render(request, 'teams/dashboard.html', {
        'team': team,
        'players': players,
        'payments': payments
    })

def all_teams(request):
    teams = Team.objects.all()
    zones = Zone.objects.all()
    
    return render(request, 'teams/all_teams.html', {
        'teams': teams,
        'zones': zones
    })

def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    players = Player.objects.filter(team=team).order_by('jersey_number')
    
    return render(request, 'teams/team_detail.html', {
        'team': team,
        'players': players
    })

def league_admin_dashboard(request):
    """Dashboard for league admin to manage all teams"""
    from django.utils import timezone
    from datetime import timedelta
    
    teams = Team.objects.all()
    recent_cutoff = timezone.now() - timedelta(days=7)
    
    context = {
        'teams_count': teams.count(),
        'active_teams': teams.filter(status='approved').count(),
        'pending_teams': teams.filter(status='pending').count(),
        'total_players': Player.objects.count(),
        'total_captains': Player.objects.filter(is_captain=True).count(),
        'paid_teams': teams.filter(payment_status=True).count(),
        'unpaid_teams': teams.filter(payment_status=False).count(),
        'recent_registrations': teams.filter(registration_date__gte=recent_cutoff).count(),
        'recent_teams': teams.order_by('-registration_date')[:10],
    }
    return render(request, 'teams/admin_dashboard.html', context)

@login_required
def update_team_kits(request, team_id=None):
    """Allow team managers to update their kit colors"""
    # If team_id provided and user is staff/admin, allow editing any team
    if team_id and request.user.is_staff:
        team = get_object_or_404(Team, id=team_id)
    # Otherwise, get the user's managed team
    elif request.user.is_authenticated and hasattr(request.user, 'managed_teams'):
        team = request.user.managed_teams.first()
        if not team:
            messages.error(request, "You are not assigned to any team.")
            return redirect('dashboard')
    else:
        messages.error(request, "You don't have permission to edit team kits.")
        return redirect('frontend:home')
    
    # Check if team is approved
    if team.status != 'approved' and not request.user.is_staff:
        messages.error(request, 'Your team must be approved before you can customize kits.')
        return redirect('teams:team_dashboard', team_id=team.id)
    
    if request.method == 'POST':
        form = TeamKitForm(request.POST, instance=team)
        if form.is_valid():
            team = form.save(commit=False)
            team.kit_colors_set = True  # mark as completed
            team.save()
            messages.success(request, '✅ Team kit colors updated successfully!')
            return redirect('teams:team_dashboard', team_id=team.id)
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = TeamKitForm(instance=team)
    
    return render(request, 'teams/select_kit.html', {
        'form': form,
        'team': team
    })

@login_required
def select_kit_colors(request):
    """Team manager selects kit colors AND images after approval"""
    # Get team managed by this user
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You are not assigned to any approved team.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Update all kit color fields from POST data
        team.home_jersey_color = request.POST.get('home_jersey_color', '#dc3545')
        team.home_shorts_color = request.POST.get('home_shorts_color', '#ffffff')
        team.home_socks_color = request.POST.get('home_socks_color', '#dc3545')
        
        team.away_jersey_color = request.POST.get('away_jersey_color', '#ffffff')
        team.away_shorts_color = request.POST.get('away_shorts_color', '#dc3545')
        team.away_socks_color = request.POST.get('away_socks_color', '#ffffff')
        
        team.third_jersey_color = request.POST.get('third_jersey_color', '')
        team.third_shorts_color = request.POST.get('third_shorts_color', '')
        team.third_socks_color = request.POST.get('third_socks_color', '')
        
        team.gk_home_jersey_color = request.POST.get('gk_home_jersey_color', '#28a745')
        team.gk_home_shorts_color = request.POST.get('gk_home_shorts_color', '#28a745')
        team.gk_home_socks_color = request.POST.get('gk_home_socks_color', '#28a745')
        
        team.gk_away_jersey_color = request.POST.get('gk_away_jersey_color', '#ffc107')
        team.gk_away_shorts_color = request.POST.get('gk_away_shorts_color', '#ffc107')
        team.gk_away_socks_color = request.POST.get('gk_away_socks_color', '#ffc107')
        
        team.gk_third_jersey_color = request.POST.get('gk_third_jersey_color', '')
        team.gk_third_shorts_color = request.POST.get('gk_third_shorts_color', '')
        team.gk_third_socks_color = request.POST.get('gk_third_socks_color', '')
        
        # Handle kit image uploads - ADD THIS SECTION
        # Outfield players kits
        if 'home_kit_image' in request.FILES and request.FILES['home_kit_image']:
            team.home_kit_image = request.FILES['home_kit_image']
        
        if 'away_kit_image' in request.FILES and request.FILES['away_kit_image']:
            team.away_kit_image = request.FILES['away_kit_image']
        
        if 'third_kit_image' in request.FILES and request.FILES['third_kit_image']:
            team.third_kit_image = request.FILES['third_kit_image']
        
        # Goalkeeper kits
        if 'gk_home_kit_image' in request.FILES and request.FILES['gk_home_kit_image']:
            team.gk_home_kit_image = request.FILES['gk_home_kit_image']
        
        if 'gk_away_kit_image' in request.FILES and request.FILES['gk_away_kit_image']:
            team.gk_away_kit_image = request.FILES['gk_away_kit_image']
        
        if 'gk_third_kit_image' in request.FILES and request.FILES['gk_third_kit_image']:
            team.gk_third_kit_image = request.FILES['gk_third_kit_image']
        
        # Mark kit colors as set
        team.kit_colors_set = True
        
        try:
            team.save()
            messages.success(request, "✅ Kit colors and images saved successfully!")
            # Redirect to team officials form instead of dashboard
            return redirect('teams:team_officials')
        except Exception as e:
            messages.error(request, f"Error saving kit colors: {str(e)}")
    
    # GET request - show the form with existing images
    return render(request, 'teams/select_kit.html', {
        'team': team
    })

@login_required
def team_manager_dashboard(request):
    """Dashboard for approved team managers"""
    # Get user's approved team
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    # Check if kit colors are set
    kit_complete = team.kit_colors_set

    # Show reminder only once for approved teams on first login
    show_kit_prompt = False
    if not kit_complete and not team.kit_setup_prompt_shown:
        show_kit_prompt = True
        team.kit_setup_prompt_shown = True
        team.save(update_fields=['kit_setup_prompt_shown'])
    
    # Get team data
    players = Player.objects.filter(team=team).order_by('jersey_number')
    player_count = players.count()
    captain = players.filter(is_captain=True).first()
    
    # Get league settings for deadlines
    settings = LeagueSettings.get_settings()
    
    context = {
        'team': team,
        'players': players,
        'player_count': player_count,
        'captain_name': captain.full_name if captain else "Not set",
        'kit_complete': kit_complete,
        'show_kit_prompt': show_kit_prompt,
        'recent_players': players.order_by('-registration_date')[:10],
        'league_settings': settings,  # Add this for consistency with home template
        'player_registration_deadline': settings.player_registration_deadline,
        'player_registration_closed_date': settings.player_registration_closed_date,
        'transfer_window_deadline': settings.transfer_window_deadline,
        'transfer_window_closed_date': settings.transfer_window_closed_date,
        'player_registration_open': settings.player_registration_open,
        'transfer_window_open': settings.transfer_window_open,
    }
    return render(request, 'dashboard/team_manager.html', context)
    return render(request, 'dashboard/team_manager.html', context)

@login_required
def add_player_action(request):
    """Handle ONLY the Add Player button"""
    # Check if player registration is open
    settings = LeagueSettings.get_settings()
    if not settings.player_registration_open:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Player Registration Closed',
            'message': 'Player registration is currently closed. Please check back later or contact the league administrator.',
            'back_url': 'teams:team_manager_dashboard',
            'deadline': settings.player_registration_deadline
        })
    
    # Get user's approved team
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    if not team.kit_colors_set:
        messages.error(request, "Please set your team kit colors first!")
        return redirect('teams:select_kit_colors')
    
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        date_of_birth = request.POST.get('date_of_birth')
        id_number = request.POST.get('id_number', '').strip()
        nationality = request.POST.get('nationality', 'Kenyan')
        position = request.POST.get('position')
        jersey_number = request.POST.get('jersey_number')
        fkf_license_number = request.POST.get('fkf_license_number', '')
        license_expiry_date = request.POST.get('license_expiry_date')
        is_captain = 'is_captain' in request.POST
        
        # Validate required fields
        if not all([first_name, last_name, date_of_birth, id_number, position, jersey_number]):
            messages.error(request, "Please fill all required fields marked with *")
            return redirect('teams:add_players_approved')
        
        try:
            # Check if ID number already exists
            if Player.objects.filter(id_number=id_number).exists():
                messages.error(request, f'ID Number {id_number} is already registered.')
                return redirect('teams:add_players_approved')
            
            # Check jersey number uniqueness for this team
            if Player.objects.filter(team=team, jersey_number=jersey_number).exists():
                messages.error(request, f'Jersey number {jersey_number} is already taken.')
                return redirect('teams:add_players_approved')
            
            # If setting as captain, remove captain status from other players
            if is_captain:
                Player.objects.filter(team=team, is_captain=True).update(is_captain=False)
            
            # Create player
            player = Player.objects.create(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                id_number=id_number,
                nationality=nationality,
                position=position,
                jersey_number=jersey_number,
                team=team,
                fkf_license_number=fkf_license_number,
                license_expiry_date=license_expiry_date if license_expiry_date else None,
                is_captain=is_captain
            )
            
            # Handle photo upload
            if 'photo' in request.FILES and request.FILES['photo']:
                player.photo = request.FILES['photo']
                player.save()
            
            messages.success(request, f'✅ Player {player.full_name} added successfully!')
            
            # ALWAYS redirect back to add players page (Add & Continue)
            return redirect('teams:add_players_approved')
                
        except Exception as e:
            messages.error(request, f'Error saving player: {str(e)}')
            return redirect('teams:add_players_approved')
    
    # If not POST, redirect to add players page
    return redirect('teams:add_players_approved')

@login_required
def add_players_to_approved_team(request):
    """Just show the form - NO POST handling here"""
    settings = LeagueSettings.get_settings()

    if not settings.player_registration_open:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Player Registration Closed',
            'message': 'Player registration is currently closed. Please check back later or contact the league admin.',
            'deadline': settings.player_registration_deadline,
            'back_url': request.META.get('HTTP_REFERER', '/'),
        })

    # Get user's approved team
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    # Check if kit colors are set
    if not team.kit_colors_set:
        messages.error(request, "Please set your team kit colors first!")
        return redirect('teams:select_kit_colors')
    
    # GET request only - show the form
    players = Player.objects.filter(team=team).order_by('jersey_number')
    player_count = players.count()
    
    return render(request, 'teams/add_players_approved.html', {
        'team': team,
        'players': players,
        'player_count': player_count
    })


# =============================================================================
# TRANSFER SYSTEM VIEWS
# =============================================================================

@login_required
def search_players(request):
    """Select team and player to request transfer using dropdowns"""
    settings = LeagueSettings.get_settings()
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')

    if not settings.transfer_window_open:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Transfer Window Closed',
            'message': 'Player transfers are currently closed. Please check back once the window reopens.',
            'deadline': settings.transfer_window_deadline,
            'back_url': request.META.get('HTTP_REFERER', '/'),
        })
    
    # Get all other teams (approved teams excluding user's team)
    all_teams = Team.objects.filter(status='approved').exclude(id=team.id).order_by('team_name')
    
    selected_team_id = request.GET.get('team_id', '')
    selected_players = []
    
    if selected_team_id:
        try:
            selected_team = Team.objects.get(id=selected_team_id, status='approved')
            # Get players from selected team (ordered by jersey number)
            selected_players = Player.objects.filter(team=selected_team).order_by('jersey_number')
        except Team.DoesNotExist:
            pass
    
    context = {
        'team': team,
        'all_teams': all_teams,
        'selected_team_id': selected_team_id,
        'selected_players': selected_players,
        'transfer_window_open': settings.transfer_window_open
    }
    return render(request, 'teams/search_players.html', context)


@login_required
def request_transfer(request, player_id):
    """Team manager requests a player transfer"""
    settings = LeagueSettings.get_settings()
    
    if not settings.transfer_window_open:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Transfer Window Closed',
            'message': 'Player transfers are currently closed. Please check back once the window reopens.',
            'deadline': settings.transfer_window_deadline,
            'back_url': request.META.get('HTTP_REFERER', '/'),
        })
    
    # Get requester's team
    to_team = Team.objects.filter(manager=request.user, status='approved').first()
    if not to_team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    # Get the player
    player = get_object_or_404(Player, id=player_id)
    from_team = player.team
    
    # Validation
    if from_team == to_team:
        messages.error(request, "This player is already in your team.")
        return redirect('teams:search_players')
    
    # Check for duplicate pending request
    if TransferRequest.objects.filter(
        player=player,
        to_team=to_team,
        status='pending_parent'
    ).exists():
        messages.error(request, f"You already have a pending transfer request for {player.full_name}.")
        return redirect('teams:search_players')
    
    # Create transfer request
    try:
        transfer = TransferRequest.objects.create(
            player=player,
            from_team=from_team,
            to_team=to_team,
            requested_by=request.user
        )
        messages.success(request, 
            f"✅ <strong>Transfer Request Successful!</strong><br>"
            f"You have successfully requested <strong>{player.full_name}</strong> "
            f"(#{player.jersey_number}, {player.get_position_display()}) from <strong>{from_team.team_name}</strong>.<br>"
            f"<small class='text-muted'>The request is now waiting for approval from {from_team.team_name}'s manager. "
            f"You will be notified once they respond to your request.</small>"
        )
    except Exception as e:
        messages.error(request, f"❌ <strong>Error:</strong> Could not create transfer request. {str(e)}")
    
    return redirect('teams:my_transfer_requests')


@login_required
def my_transfer_requests(request):
    """View all transfer requests (incoming and outgoing)"""
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    # Outgoing: Players I want to bring in
    outgoing_requests = TransferRequest.objects.filter(
        to_team=team
    ).select_related('player', 'from_team', 'requested_by').order_by('-request_date')
    
    # Incoming: Players others want from my team
    incoming_requests = TransferRequest.objects.filter(
        from_team=team,
        status='pending_parent'
    ).select_related('player', 'to_team', 'requested_by').order_by('-request_date')
    
    context = {
        'team': team,
        'outgoing_requests': outgoing_requests,
        'incoming_requests': incoming_requests,
        'pending_incoming_count': incoming_requests.count()
    }
    return render(request, 'teams/transfer_requests.html', context)


@login_required
def approve_transfer(request, transfer_id):
    """Parent club approves transfer request"""
    transfer = get_object_or_404(TransferRequest, id=transfer_id)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    # Validate ownership
    if transfer.from_team != team:
        messages.error(request, "You can only approve transfers for your own team.")
        return redirect('teams:my_transfer_requests')
    
    # Validate status
    if transfer.status != 'pending_parent':
        messages.error(request, "This transfer request has already been processed.")
        return redirect('teams:my_transfer_requests')
    
    # Approve and execute transfer
    transfer.approve_by_parent(user=request.user, execute_transfer=True)
    
    messages.success(request, 
        f"✅ Transfer approved! {transfer.player.full_name} has been transferred to {transfer.to_team.team_name}."
    )
    return redirect('teams:my_transfer_requests')


@login_required
def reject_transfer(request, transfer_id):
    """Parent club rejects transfer request with reason"""
    transfer = get_object_or_404(TransferRequest, id=transfer_id)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    # Validate ownership
    if transfer.from_team != team:
        messages.error(request, "You can only reject transfers for your own team.")
        return redirect('teams:my_transfer_requests')
    
    # Validate status
    if transfer.status != 'pending_parent':
        messages.error(request, "This transfer request has already been processed.")
        return redirect('teams:my_transfer_requests')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "Please provide a reason for rejection.")
            return redirect('teams:my_transfer_requests')
        
        transfer.reject_by_parent(user=request.user, reason=reason)
        
        messages.success(request, 
            f"❌ Transfer rejected. {transfer.to_team.team_name} has been notified."
        )
        return redirect('teams:my_transfer_requests')
    
    # Show rejection form
    return render(request, 'teams/reject_transfer.html', {
        'transfer': transfer,
        'team': team
    })


@login_required
def cancel_transfer(request, transfer_id):
    """Requester cancels their transfer request"""
    transfer = get_object_or_404(TransferRequest, id=transfer_id)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    # Validate requester
    if transfer.to_team != team:
        messages.error(request, "You can only cancel your own transfer requests.")
        return redirect('teams:my_transfer_requests')
    
    if transfer.cancel_by_requester():
        messages.success(request, f"Transfer request for {transfer.player.full_name} cancelled.")
    else:
        messages.error(request, "Cannot cancel this transfer request (already processed).")
    
    return redirect('teams:my_transfer_requests')


# =============================================================================
# TEAM OFFICIALS VIEWS
# =============================================================================

@login_required
def team_officials(request):
    """Manage team officials - can be accessed anytime after approval"""
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    # Get existing officials
    officials = TeamOfficial.objects.filter(team=team).order_by('position')
    
    # Check which positions are filled
    filled_positions = officials.values_list('position', flat=True)
    required_positions = ['head_coach', 'assistant_coach', 'goalkeeper_coach', 'team_doctor', 'team_patron']
    missing_positions = [pos for pos in required_positions if pos not in filled_positions]
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_official':
            form = TeamOfficialForm(request.POST, request.FILES)
            if form.is_valid():
                official = form.save(commit=False)
                official.team = team
                try:
                    official.save()
                    messages.success(request, f"\u2705 {official.get_position_display()} added successfully!")
                    return redirect('teams:team_officials')
                except Exception as e:
                    messages.error(request, f"Error: {str(e)}")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        
        elif action == 'continue':
            # Check if all required positions are filled
            if missing_positions:
                messages.warning(request, f"Please add: {', '.join([dict(TeamOfficial.POSITION_CHOICES)[pos] for pos in missing_positions])}")
            else:
                messages.success(request, "\u2705 All team officials registered! You can now add players.")
                return redirect('teams:add_players_approved')
    
    form = TeamOfficialForm()
    
    context = {
        'team': team,
        'officials': officials,
        'form': form,
        'missing_positions': missing_positions,
        'filled_count': officials.count(),
        'total_required': len(required_positions),
    }
    return render(request, 'teams/team_officials.html', context)


@login_required
def delete_official(request, official_id):
    """Delete a team official"""
    official = get_object_or_404(TeamOfficial, id=official_id)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if official.team != team:
        messages.error(request, "You can only delete officials from your own team.")
        return redirect('teams:team_officials')
    
    official_name = official.full_name
    official.delete()
    messages.success(request, f"\u274c {official_name} removed.")
    return redirect('teams:team_officials')