# referees/matchday_views.py
"""
Views for Matchday Squad Management System
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from datetime import timedelta

from matches.models import Match
from teams.models import Team, Player
from .models import (
    MatchdaySquad, SquadPlayer, SubstitutionRequest, 
    Referee, MatchOfficials
)


# ========== TEAM MANAGER VIEWS ==========

@login_required
def team_matchday_squad_list(request):
    """Team manager's view of upcoming matches requiring squad submission"""
    # Get team from managed_teams relationship
    if hasattr(request.user, 'managed_teams'):
        team = request.user.managed_teams.first()
    else:
        team = None
    
    if not team:
        messages.error(request, "You need to be associated with a team to manage squads.")
        return redirect('dashboard')
    
    # Get matches within next 7 days that need squads
    today = timezone.now()
    upcoming_matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        match_date__gte=today.date(),
        match_date__lte=(today + timedelta(days=7)).date(),
        status='scheduled'
    ).order_by('match_date', 'kickoff_time')
    
    matches_data = []
    for match in upcoming_matches:
        squad, created = MatchdaySquad.objects.get_or_create(
            match=match,
            team=team
        )
        
        # Calculate submission window
        if match.match_date and match.kickoff_time:
            # Handle kickoff_time as string or time object
            kickoff_time = match.kickoff_time
            if isinstance(kickoff_time, str):
                try:
                    from datetime import datetime
                    kickoff_time = datetime.strptime(kickoff_time, '%H:%M:%S').time()
                except (ValueError, AttributeError):
                    try:
                        kickoff_time = datetime.strptime(kickoff_time, '%H:%M').time()
                    except (ValueError, AttributeError):
                        can_submit = False
                        submission_opens = None
                        matches_data.append({
                            'match': match,
                            'squad': squad,
                            'can_submit': can_submit,
                            'submission_opens': submission_opens,
                            'starting_count': squad.squad_players.filter(is_starting=True).count(),
                            'subs_count': squad.squad_players.filter(is_starting=False).count(),
                        })
                        continue
            
            match_datetime = timezone.make_aware(
                timezone.datetime.combine(match.match_date, kickoff_time)
            )
            submission_opens = match_datetime - timedelta(hours=2)
            can_submit = today >= submission_opens and not squad.is_locked()
        else:
            can_submit = False
            submission_opens = None
        
        matches_data.append({
            'match': match,
            'squad': squad,
            'can_submit': can_submit,
            'submission_opens': submission_opens,
            'starting_count': squad.squad_players.filter(is_starting=True).count(),
            'subs_count': squad.squad_players.filter(is_starting=False).count(),
        })
    
    context = {
        'team': team,
        'matches_data': matches_data,
    }
    return render(request, 'referees/matchday/team_squad_list.html', context)


@login_required
def submit_matchday_squad(request, match_id):
    """Team manager submits matchday squad"""
    match = get_object_or_404(Match, id=match_id)
    
    # Get team from managed_teams relationship
    if hasattr(request.user, 'managed_teams'):
        team = request.user.managed_teams.first()
    else:
        team = None
    
    if not team:
        messages.error(request, "You need to be associated with a team to submit squads.")
        return redirect('dashboard')
    
    # Check if team is playing in this match
    if team not in [match.home_team, match.away_team]:
        messages.error(request, "Your team is not playing in this match.")
        return redirect('teams:team_manager_dashboard')
    
    # Get or create squad
    squad, created = MatchdaySquad.objects.get_or_create(
        match=match,
        team=team
    )
    
    # Check if can submit
    if squad.is_locked():
        messages.error(request, "This squad is locked and cannot be modified.")
        return redirect('referees:team_matchday_squad_list')
    
    if not squad.can_submit():
        messages.warning(request, "Squad submission window has not opened yet (opens 4 hours before kick-off).")
        return redirect('referees:team_matchday_squad_list')
    
    # Get all eligible players (not suspended)
    eligible_players = team.players.filter(is_suspended=False).order_by('position', 'jersey_number')
    
    # Get current squad selections
    selected_starting = list(squad.squad_players.filter(is_starting=True).values_list('player_id', flat=True))
    selected_subs = list(squad.squad_players.filter(is_starting=False).values_list('player_id', flat=True))
    
    if request.method == 'POST':
        # Get selected players from form
        starting_ids = request.POST.getlist('starting_players')
        sub_ids = request.POST.getlist('substitute_players')
        
        # Validate counts
        if len(starting_ids) < 7:
            messages.error(request, f"You must select at least 7 starting players. You selected {len(starting_ids)}.")
            return render(request, 'referees/matchday/submit_squad.html', {
                'match': match, 'squad': squad, 'team': team,
                'eligible_players': eligible_players,
                'selected_starting': selected_starting,
                'selected_subs': selected_subs,
            })
        
        if len(starting_ids) > 11:
            messages.error(request, f"You cannot select more than 11 starting players. You selected {len(starting_ids)}.")
            return render(request, 'referees/matchday/submit_squad.html', {
                'match': match, 'squad': squad, 'team': team,
                'eligible_players': eligible_players,
                'selected_starting': selected_starting,
                'selected_subs': selected_subs,
            })
        
        if len(sub_ids) > 14:
            messages.error(request, f"You cannot select more than 14 substitute players. You selected {len(sub_ids)}.")
            return render(request, 'referees/matchday/submit_squad.html', {
                'match': match, 'squad': squad, 'team': team,
                'eligible_players': eligible_players,
                'selected_starting': selected_starting,
                'selected_subs': selected_subs,
            })
        
        # Check for duplicates - player cannot be in both lists
        all_selected = starting_ids + sub_ids
        if len(all_selected) != len(set(all_selected)):
            # Find which players are duplicated
            duplicates = set([pid for pid in all_selected if all_selected.count(pid) > 1])
            duplicate_players = Player.objects.filter(id__in=duplicates)
            duplicate_names = ', '.join([p.full_name for p in duplicate_players])
            messages.error(request, f"Player(s) cannot be selected in both starting lineup AND substitutes: {duplicate_names}")
            return render(request, 'referees/matchday/submit_squad.html', {
                'match': match, 'squad': squad, 'team': team,
                'eligible_players': eligible_players,
                'selected_starting': selected_starting,
                'selected_subs': selected_subs,
            })
        
        # Validate goalkeeper in starting 11
        starting_players = Player.objects.filter(id__in=starting_ids)
        starting_gks = starting_players.filter(position='GK').count()
        if starting_gks < 1:
            messages.error(request, "Starting lineup must include at least 1 goalkeeper.")
            return render(request, 'referees/matchday/submit_squad.html', {
                'match': match, 'squad': squad, 'team': team,
                'eligible_players': eligible_players,
                'selected_starting': selected_starting,
                'selected_subs': selected_subs,
            })
        
        # Validate goalkeeper in substitutes
        sub_players = Player.objects.filter(id__in=sub_ids)
        sub_gks = sub_players.filter(position='GK').count()
        if sub_gks < 1:
            messages.error(request, "Substitutes must include at least 1 goalkeeper.")
            return render(request, 'referees/matchday/submit_squad.html', {
                'match': match, 'squad': squad, 'team': team,
                'eligible_players': eligible_players,
                'selected_starting': selected_starting,
                'selected_subs': selected_subs,
            })
        
        # Clear existing squad
        squad.squad_players.all().delete()
        
        # Add starting 11
        for i, player_id in enumerate(starting_ids):
            player = Player.objects.get(id=player_id)
            SquadPlayer.objects.create(
                squad=squad,
                player=player,
                is_starting=True,
                position_order=i,
                jersey_number=player.jersey_number
            )
        
        # Add substitutes
        for player_id in sub_ids:
            player = Player.objects.get(id=player_id)
            SquadPlayer.objects.create(
                squad=squad,
                player=player,
                is_starting=False,
                jersey_number=player.jersey_number
            )
        
        # Update squad status
        squad.status = 'submitted'
        squad.submitted_at = timezone.now()
        squad.submitted_by = request.user
        squad.save()
        
        messages.success(request, f"Matchday squad submitted successfully! Awaiting referee approval.")
        return redirect('referees:team_matchday_squad_list')
    
    context = {
        'match': match,
        'squad': squad,
        'team': team,
        'eligible_players': eligible_players,
        'selected_starting': selected_starting,
        'selected_subs': selected_subs,
    }
    return render(request, 'referees/matchday/submit_squad.html', context)


# ========== MAIN REFEREE VIEWS ==========

@login_required
def referee_squad_approval_list(request):
    """Main referee's list of matches needing squad approval"""
    try:
        referee = request.user.referee_profile
    except AttributeError:
        messages.error(request, "You need to be a registered referee.")
        return redirect('referees:referee_dashboard')
    
    # Get matches where this referee is the main referee
    today = timezone.now()
    appointments = MatchOfficials.objects.filter(
        main_referee=referee,
        match__match_date__gte=today.date(),
        match__status='scheduled'
    ).select_related('match', 'match__home_team', 'match__away_team').order_by('match__match_date')
    
    matches_data = []
    for appointment in appointments:
        match = appointment.match
        
        # Get squads for both teams
        home_squad = MatchdaySquad.objects.filter(match=match, team=match.home_team).first()
        away_squad = MatchdaySquad.objects.filter(match=match, team=match.away_team).first()
        
        matches_data.append({
            'match': match,
            'home_squad': home_squad,
            'away_squad': away_squad,
            'can_approve': not match.has_kicked_off() if hasattr(match, 'has_kicked_off') else True,
        })
    
    context = {
        'referee': referee,
        'matches_data': matches_data,
    }
    return render(request, 'referees/matchday/referee_approval_list.html', context)


@login_required
def approve_matchday_squads(request, match_id):
    """Main referee approves both teams' squads"""
    match = get_object_or_404(Match, id=match_id)
    
    try:
        referee = request.user.referee_profile
    except AttributeError:
        messages.error(request, "You need to be a registered referee.")
        return redirect('referees:referee_dashboard')
    
    # Check if this referee is the main referee for this match
    try:
        appointment = MatchOfficials.objects.get(match=match, main_referee=referee)
    except MatchOfficials.DoesNotExist:
        messages.error(request, "You are not the main referee for this match.")
        return redirect('referees:referee_dashboard')
    
    # Get squads
    home_squad = get_object_or_404(MatchdaySquad, match=match, team=match.home_team)
    away_squad = get_object_or_404(MatchdaySquad, match=match, team=match.away_team)
    
    # Check if squads are submitted
    if home_squad.status != 'submitted':
        messages.warning(request, f"{match.home_team.team_name} has not submitted their squad yet.")
    
    if away_squad.status != 'submitted':
        messages.warning(request, f"{match.away_team.team_name} has not submitted their squad yet.")
    
    if request.method == 'POST':
        action = request.POST.get('action')
        team_to_approve = request.POST.get('team')  # 'home' or 'away'
        
        if action == 'approve_team':
            # Approve one team's squad at a time
            if team_to_approve == 'home':
                squad = home_squad
            elif team_to_approve == 'away':
                squad = away_squad
            else:
                messages.error(request, "Invalid team selection.")
                return redirect('referees:approve_matchday_squads', match_id=match.id)
            
            if squad.status == 'submitted':
                # Approve all players in the squad
                for player in squad.squad_players.all():
                    player.is_approved = True
                    player.approved_at = timezone.now()
                    player.save()
                
                squad.status = 'approved'
                squad.approved_at = timezone.now()
                squad.approved_by = referee
                squad.save()
                
                # Auto-populate match report form with approved squad
                from referees.models import StartingLineup, ReservePlayer
                
                # Clear existing entries for this team in this match (if any)
                StartingLineup.objects.filter(match=match, team=squad.team).delete()
                ReservePlayer.objects.filter(match=match, team=squad.team).delete()
                
                # Add starting XI to match report form
                for squad_player in squad.squad_players.filter(is_starting=True):
                    StartingLineup.objects.create(
                        match=match,
                        team=squad.team,
                        player=squad_player.player,
                        jersey_number=squad_player.player.jersey_number,
                        position=squad_player.player.get_position_display()
                    )
                
                # Add substitutes to match report form
                for squad_player in squad.squad_players.filter(is_starting=False):
                    ReservePlayer.objects.create(
                        match=match,
                        team=squad.team,
                        player=squad_player.player,
                        jersey_number=squad_player.player.jersey_number
                    )
                
                messages.success(request, f"{squad.team.team_name}'s squad has been approved and match report populated!")
            else:
                messages.warning(request, f"{squad.team.team_name}'s squad is not ready for approval.")
            
            return redirect('referees:approve_matchday_squads', match_id=match.id)
        
        elif action == 'approve_both':
            # Approve both teams' squads at once
            approved_count = 0
            for squad in [home_squad, away_squad]:
                if squad.status == 'submitted':
                    for player in squad.squad_players.all():
                        player.is_approved = True
                        player.approved_at = timezone.now()
                        player.save()
                    
                    squad.status = 'approved'
                    squad.approved_at = timezone.now()
                    squad.approved_by = referee
                    squad.save()
                    
                    # Auto-populate match report form with approved squad
                    from referees.models import StartingLineup, ReservePlayer
                    
                    # Clear existing entries for this team in this match (if any)
                    StartingLineup.objects.filter(match=match, team=squad.team).delete()
                    ReservePlayer.objects.filter(match=match, team=squad.team).delete()
                    
                    # Add starting XI to match report form
                    for squad_player in squad.squad_players.filter(is_starting=True):
                        StartingLineup.objects.create(
                            match=match,
                            team=squad.team,
                            player=squad_player.player,
                            jersey_number=squad_player.player.jersey_number,
                            position=squad_player.player.get_position_display()
                        )
                    
                    # Add substitutes to match report form
                    for squad_player in squad.squad_players.filter(is_starting=False):
                        ReservePlayer.objects.create(
                            match=match,
                            team=squad.team,
                            player=squad_player.player,
                            jersey_number=squad_player.player.jersey_number
                        )
                    
                    approved_count += 1
            
            if approved_count > 0:
                messages.success(request, f"{approved_count} team(s) approved and match report populated!")
            else:
                messages.warning(request, "No teams ready for approval.")
            
            return redirect('referees:referee_squad_approval_list')
    
    context = {
        'match': match,
        'referee': referee,
        'home_squad': home_squad,
        'away_squad': away_squad,
        'home_starting': home_squad.get_starting_eleven(),
        'home_subs': home_squad.get_substitutes(),
        'away_starting': away_squad.get_starting_eleven(),
        'away_subs': away_squad.get_substitutes(),
    }
    return render(request, 'referees/matchday/referee_approve_squads.html', context)


# ========== FOURTH OFFICIAL / RESERVE REFEREE VIEWS ==========

@login_required
def reserve_referee_substitutions(request, match_id):
    """Reserve referee/main referee/reserve referee manages substitutions during match"""
    match = get_object_or_404(Match, id=match_id)
    
    try:
        referee = request.user.referee_profile
    except AttributeError:
        messages.error(request, "You need to be a registered referee.")
        return redirect('referees:referee_dashboard')
    
    # Check if this referee is main referee or reserve referee (fourth official) for this match
    # Both main referee and reserve referee can approve substitutions
    appointment = MatchOfficials.objects.filter(
        match=match
    ).filter(
        Q(main_referee=referee) | Q(fourth_official=referee)
    ).first()
    
    if not appointment:
        messages.error(request, "You are not assigned to this match as an official.")
        return redirect('referees:referee_dashboard')
    
    # Determine referee role
    is_main_referee = appointment.main_referee == referee
    is_reserve = appointment.fourth_official == referee
    # Both main referee and reserve can approve substitutions
    can_approve_subs = is_main_referee or is_reserve
    
    # Get squads
    home_squad = MatchdaySquad.objects.filter(match=match, team=match.home_team).first()
    away_squad = MatchdaySquad.objects.filter(match=match, team=match.away_team).first()
    
    # Get substitution requests
    home_requests = SubstitutionRequest.objects.filter(match=match, team=match.home_team, status='pending').order_by('-requested_at')
    away_requests = SubstitutionRequest.objects.filter(match=match, team=match.away_team, status='pending').order_by('-requested_at')
    
# Calculate used opportunities (count completed substitutions)
    home_opportunities_used = SubstitutionRequest.objects.filter(
        match=match, 
        team=match.home_team, 
        status='completed'
    ).count()
    
    away_opportunities_used = SubstitutionRequest.objects.filter(
        match=match, 
        team=match.away_team, 
        status='completed'
    ).count()
    
    # Calculate progress percentages
    home_progress_percentage = min(home_opportunities_used * 33.33, 100)
    away_progress_percentage = min(away_opportunities_used * 33.33, 100)
    
    # Prepare squad data for JavaScript
    def get_squad_data(squad):
        if not squad:
            return {'starting': [], 'subs': []}
        starting = [{'id': sp.player.id, 'jersey': sp.jersey_number, 'name': sp.player.full_name} 
                   for sp in squad.squad_players.filter(is_starting=True)]
        subs = [{'id': sp.player.id, 'jersey': sp.jersey_number, 'name': sp.player.full_name} 
               for sp in squad.squad_players.filter(is_starting=False)]
        return {'starting': starting, 'subs': subs}
    
    # Get completed substitutions for display
    completed_subs = SubstitutionRequest.objects.filter(
        match=match, 
        status='completed'
    ).order_by('minute')
    
    # Calculate used substitutions (for display)
    home_subs_count = SubstitutionRequest.objects.filter(
        match=match, 
        team=match.home_team, 
        status='completed'
    ).count()
    
    away_subs_count = SubstitutionRequest.objects.filter(
        match=match, 
        team=match.away_team, 
        status='completed'
    ).count()
    
    # Check for concussion subs
    home_concussion_sub = SubstitutionRequest.objects.filter(
        match=match, 
        team=match.home_team, 
        status='completed',
        sub_type='concussion'
    ).exists()
    
    away_concussion_sub = SubstitutionRequest.objects.filter(
        match=match, 
        team=match.away_team, 
        status='completed',
        sub_type='concussion'
    ).exists()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        request_id = request.POST.get('request_id')
        
        if action == 'effect_substitution':
            sub_request = get_object_or_404(SubstitutionRequest, id=request_id)
            minute = request.POST.get('minute')
            
            if not minute:
                messages.error(request, "Please specify the minute for the substitution.")
            else:
                sub_request.minute = int(minute)
                sub_request.status = 'completed'
                sub_request.effected_at = timezone.now()
                sub_request.effected_by = referee
                sub_request.save()
                
                # Create or update SubstitutionOpportunity
                from .models import SubstitutionOpportunity
                is_halftime = 45 <= int(minute) <= 60
                opportunity, created = SubstitutionOpportunity.objects.get_or_create(
                    match=match,
                    team=sub_request.team,
                    minute=int(minute),
                    defaults={
                        'opportunity_number': SubstitutionOpportunity.objects.filter(
                            match=match, 
                            team=sub_request.team, 
                            is_halftime=False
                        ).count() + 1,
                        'is_halftime': is_halftime
                    }
                )
                opportunity.substitutions.add(sub_request)
                
                # Create Substitution record for match report
                from .models import Substitution
                Substitution.objects.create(
                    match=match,
                    team=sub_request.team,
                    minute=int(minute),
                    player_out=sub_request.player_out,
                    player_in=sub_request.player_in,
                    jersey_out=sub_request.player_out.jersey_number,
                    jersey_in=sub_request.player_in.jersey_number,
                )
                
                messages.success(request, f"Substitution completed: {sub_request.player_out.full_name} → {sub_request.player_in.full_name}")
                return redirect('referees:reserve_referee_substitutions', match_id=match.id)
    
    # Prepare squad data for JavaScript
    def get_squad_data(squad):
        if not squad:
            return {'starting': [], 'subs': []}
        starting = [{'id': sp.player.id, 'jersey': sp.jersey_number, 'name': sp.player.full_name} 
                   for sp in squad.squad_players.filter(is_starting=True)]
        subs = [{'id': sp.player.id, 'jersey': sp.jersey_number, 'name': sp.player.full_name} 
               for sp in squad.squad_players.filter(is_starting=False)]
        return {'starting': starting, 'subs': subs}
    
    home_squad_json = json.dumps(get_squad_data(home_squad))
    away_squad_json = json.dumps(get_squad_data(away_squad))
    
    context = {
        'match': match,
        'referee': referee,
        'is_main_referee': is_main_referee,
        'is_reserve_referee': is_reserve,
        'can_approve_subs': can_approve_subs,
        'home_squad': home_squad,
        'away_squad': away_squad,
        'home_squad_json': home_squad_json,
        'away_squad_json': away_squad_json,
        'home_requests': home_requests,
        'away_requests': away_requests,
        'home_opportunities': home_opportunities_used,
        'away_opportunities': away_opportunities_used,
        'home_opportunities_used': home_opportunities_used,
        'away_opportunities_used': away_opportunities_used,
        'home_progress_percentage': home_progress_percentage,
        'away_progress_percentage': away_progress_percentage,
        'completed_subs': completed_subs,
        'home_subs_count': home_subs_count,
        'away_subs_count': away_subs_count,
        'home_concussion_sub': home_concussion_sub,
        'away_concussion_sub': away_concussion_sub,
    }
    return render(request, 'referees/matchday/reserve_referee_subs.html', context)


@login_required
@require_http_methods(["POST"])
def activate_concussion_substitute(request, match_id):
    """Referee activates concussion substitute (6th sub)"""
    match = get_object_or_404(Match, id=match_id)
    
    try:
        referee = request.user.referee_profile
    except AttributeError:
        messages.error(request, 'Not a registered referee.')
        return redirect('referees:reserve_referee_substitutions', match_id=match.id)
    
    # Check if this referee is main referee or reserve referee for this match
    appointment = MatchOfficials.objects.filter(
        match=match
    ).filter(
        Q(main_referee=referee) | Q(fourth_official=referee)
    ).first()
    
    if not appointment:
        messages.error(request, 'You are not authorized to activate concussion substitutes for this match.')
        return redirect('referees:reserve_referee_substitutions', match_id=match.id)
    
    # Get data from request
    team_id = request.POST.get('team_id')
    player_out_id = request.POST.get('player_out_id')
    player_in_id = request.POST.get('player_in_id')
    minute = request.POST.get('minute')
    
    if not all([team_id, player_out_id, player_in_id, minute]):
        messages.error(request, 'All fields are required.')
        return redirect('referees:reserve_referee_substitutions', match_id=match.id)
    
    try:
        team = get_object_or_404(Team, id=team_id)
        player_out = get_object_or_404(Player, id=player_out_id)
        player_in = get_object_or_404(Player, id=player_in_id)
        squad = get_object_or_404(MatchdaySquad, match=match, team=team)
    except:
        messages.error(request, 'Invalid team or player selection.')
        return redirect('referees:reserve_referee_substitutions', match_id=match.id)
    
    # Create concussion substitution request
    sub_request = SubstitutionRequest.objects.create(
        match=match,
        squad=squad,
        team=team,
        player_out=player_out,
        player_in=player_in,
        minute=int(minute),
        sub_type='concussion',
        status='completed',
        requested_by=request.user,
        effected_at=timezone.now(),
        effected_by=referee,
        notes='Concussion substitute activated by referee'
    )
    
    # Create Substitution record for match report
    from .models import Substitution
    Substitution.objects.create(
        match=match,
        team=team,
        minute=int(minute),
        player_out=player_out,
        player_in=player_in,
        jersey_out=player_out.jersey_number,
        jersey_in=player_in.jersey_number,
    )
    
    messages.success(request, f'Concussion substitute activated: {player_out.full_name} → {player_in.full_name}')
    return redirect('referees:reserve_referee_substitutions', match_id=match.id)


@login_required
def team_request_substitution(request, match_id):
    """Team manager requests substitution during match (only after kickoff)"""
    match = get_object_or_404(Match, id=match_id)
    
    # Get team from managed_teams relationship
    if hasattr(request.user, 'managed_teams'):
        team = request.user.managed_teams.first()
    else:
        team = None
    
    if not team:
        messages.error(request, "You need to be a team manager to request substitutions.")
        return redirect('dashboard')
    
    # Check if team is playing in this match
    if team not in [match.home_team, match.away_team]:
        messages.error(request, "Your team is not playing in this match.")
        return redirect('teams:team_manager_dashboard')
    
    # Get squad
    squad = get_object_or_404(MatchdaySquad, match=match, team=team, status='approved')
    
    # Check if match has started (substitution requests only available after kickoff)
    if match.match_date and match.kickoff_time:
        kickoff_time = match.kickoff_time
        if isinstance(kickoff_time, str):
            try:
                from datetime import datetime
                kickoff_time = datetime.strptime(kickoff_time, '%H:%M:%S').time()
            except (ValueError, AttributeError):
                try:
                    kickoff_time = datetime.strptime(kickoff_time, '%H:%M').time()
                except (ValueError, AttributeError):
                    messages.error(request, "Invalid kickoff time format.")
                    return redirect('teams:team_manager_dashboard')
        
        match_datetime = timezone.make_aware(
            timezone.datetime.combine(match.match_date, kickoff_time)
        )
        
        if timezone.now() < match_datetime:
            messages.warning(request, "Substitution requests are only available after match kickoff.")
            return redirect('referees:team_matchday_squad_list')
    
    # Get current squad players
    starting_players = squad.squad_players.filter(is_starting=True).select_related('player')
    substitute_players = squad.squad_players.filter(is_starting=False).select_related('player')
    
    # Get pending and completed substitution requests
    pending_requests = SubstitutionRequest.objects.filter(
        match=match, team=team, status='pending'
    ).select_related('player_out', 'player_in')
    
    completed_subs = SubstitutionRequest.objects.filter(
        match=match, team=team, status='completed'
    ).select_related('player_out', 'player_in')
    
    # Calculate remaining substitutions
    normal_subs_used = completed_subs.filter(sub_type='normal').count()
    remaining_subs = 5 - normal_subs_used
    
    if request.method == 'POST':
        player_out_id = request.POST.get('player_out')
        player_in_id = request.POST.get('player_in')
        sub_type = request.POST.get('sub_type', 'normal')
        notes = request.POST.get('notes', '')
        
        if not player_out_id or not player_in_id:
            messages.error(request, "Please select both players for substitution.")
        elif player_out_id == player_in_id:
            messages.error(request, "Cannot substitute a player for themselves.")
        else:
            player_out = get_object_or_404(Player, id=player_out_id)
            player_in = get_object_or_404(Player, id=player_in_id)
            
            # Validate substitution
            if not squad.squad_players.filter(player=player_out).exists():
                messages.error(request, f"{player_out.full_name} is not in the matchday squad.")
            elif not squad.squad_players.filter(player=player_in, is_starting=False).exists():
                messages.error(request, f"{player_in.full_name} is not available as a substitute.")
            elif remaining_subs <= 0 and sub_type == 'normal':
                messages.error(request, "You have used all 5 substitutions.")
            else:
                # Create substitution request
                SubstitutionRequest.objects.create(
                    match=match,
                    squad=squad,
                    team=team,
                    player_out=player_out,
                    player_in=player_in,
                    sub_type=sub_type,
                    status='pending',
                    requested_by=request.user,
                    notes=notes
                )
                
                messages.success(request, 
                    f"Substitution request submitted: {player_out.full_name} → {player_in.full_name}. "
                    "Awaiting referee approval."
                )
                return redirect('referees:team_request_substitution', match_id=match.id)
    
    context = {
        'match': match,
        'team': team,
        'squad': squad,
        'starting_players': starting_players,
        'substitute_players': substitute_players,
        'pending_requests': pending_requests,
        'completed_subs': completed_subs,
        'remaining_subs': remaining_subs,
    }
    return render(request, 'referees/matchday/team_request_substitution.html', context)
