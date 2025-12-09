from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import Referee, MatchReport
from matches.models import Match, Goal, Card
from teams.models import Player
from .forms import (
    RefereeRegistrationForm, MatchReportForm,
    GoalForm, CardForm, MatchResultForm
)

@login_required
def referee_dashboard(request):
    """Referee dashboard"""
    try:
        referee = Referee.objects.get(user=request.user)
    except Referee.DoesNotExist:
        messages.error(request, 'You are not registered as a referee.')
        return redirect('home')
    
    # Get matches assigned to this referee
    assigned_matches = Match.objects.filter(
        referee=referee,
        status__in=['scheduled', 'ongoing']
    ).order_by('match_date')
    
    # Get submitted reports
    submitted_reports = MatchReport.objects.filter(
        referee=referee,
        status='submitted'
    )
    
    # Get draft reports
    draft_reports = MatchReport.objects.filter(
        referee=referee,
        status='draft'
    )
    
    context = {
        'referee': referee,
        'assigned_matches': assigned_matches,
        'submitted_reports': submitted_reports,
        'draft_reports': draft_reports,
    }
    return render(request, 'referees/dashboard.html', context)

@login_required
def referee_registration(request):
    """Register as a referee"""
    if hasattr(request.user, 'referee'):
        messages.info(request, 'You are already registered as a referee.')
        return redirect('referee_dashboard')
    
    if request.method == 'POST':
        form = RefereeRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            referee = form.save(commit=False)
            referee.user = request.user
            referee.save()
            
            messages.success(request, 'Referee registration successful!')
            return redirect('referee_dashboard')
    else:
        form = RefereeRegistrationForm()
    
    return render(request, 'referees/register.html', {'form': form})

@login_required
def submit_match_report(request, match_id):
    """Submit match report with goals and cards"""
    match = get_object_or_404(Match, id=match_id)
    
    # Check if user is assigned as referee for this match
    try:
        referee = Referee.objects.get(user=request.user)
    except Referee.DoesNotExist:
        messages.error(request, 'You are not registered as a referee.')
        return redirect('home')
    
    if match.referee != referee:
        messages.error(request, 'You are not assigned as referee for this match.')
        return redirect('referee_dashboard')
    
    # Get or create match report
    match_report, created = MatchReport.objects.get_or_create(
        match=match,
        defaults={'referee': referee}
    )
    
    # Forms for goals and cards
    GoalFormSet = forms.inlineformset_factory(
        MatchReport, Goal,
        form=GoalForm,
        extra=1,
        can_delete=True
    )
    
    CardFormSet = forms.inlineformset_factory(
        MatchReport, Card,
        form=CardForm,
        extra=1,
        can_delete=True
    )
    
    if request.method == 'POST':
        report_form = MatchReportForm(request.POST, instance=match_report)
        result_form = MatchResultForm(request.POST, instance=match)
        goal_formset = GoalFormSet(
            request.POST,
            instance=match_report,
            form_kwargs={'match': match}
        )
        card_formset = CardFormSet(
            request.POST,
            instance=match_report,
            form_kwargs={'match': match}
        )
        
        if all([
            report_form.is_valid(),
            result_form.is_valid(),
            goal_formset.is_valid(),
            card_formset.is_valid()
        ]):
            # Save match result
            match_result = result_form.save(commit=False)
            match_result.status = 'completed'
            match_result.save()
            
            # Save report
            report = report_form.save(commit=False)
            report.status = 'submitted'
            report.submitted_at = timezone.now()
            report.save()
            
            # Save goals and cards
            goal_formset.save()
            card_formset.save()
            
            # Update player statistics
            update_player_stats(match)
            
            # Update league table
            from matches.utils import update_league_table
            update_league_table(match)
            
            # Check suspensions
            from matches.utils import check_suspensions
            check_suspensions()
            
            messages.success(request, 'Match report submitted successfully!')
            return redirect('referee_dashboard')
    else:
        report_form = MatchReportForm(instance=match_report)
        result_form = MatchResultForm(instance=match)
        goal_formset = GoalFormSet(
            instance=match_report,
            form_kwargs={'match': match}
        )
        card_formset = CardFormSet(
            instance=match_report,
            form_kwargs={'match': match}
        )
    
    # Get players for both teams
    home_players = Player.objects.filter(team=match.home_team)
    away_players = Player.objects.filter(team=match.away_team)
    
    context = {
        'match': match,
        'report_form': report_form,
        'result_form': result_form,
        'goal_formset': goal_formset,
        'card_formset': card_formset,
        'home_players': home_players,
        'away_players': away_players,
    }
    return render(request, 'referees/match_report.html', context)

def update_player_stats(match):
    """Update player statistics after match"""
    # Update goals for players
    goals = Goal.objects.filter(match=match)
    for goal in goals:
        if not goal.is_own_goal:
            goal.scorer.goals_scored += 1
            goal.scorer.save()
    
    # Update cards for players
    cards = Card.objects.filter(match=match)
    for card in cards:
        if card.card_type == 'yellow':
            card.player.yellow_cards += 1
        elif card.card_type == 'red':
            card.player.red_cards += 1
        card.player.save()
    
    # Update matches played for all players who participated
    # (This is simplified - in reality, track actual participants)
    home_players = Player.objects.filter(team=match.home_team)
    away_players = Player.objects.filter(team=match.away_team)
    
    for player in list(home_players) + list(away_players):
        player.matches_played += 1
        player.save()

@login_required
def referee_matches(request):
    """View all matches assigned to referee"""
    try:
        referee = Referee.objects.get(user=request.user)
    except Referee.DoesNotExist:
        messages.error(request, 'You are not registered as a referee.')
        return redirect('home')
    
    matches = Match.objects.filter(referee=referee).order_by('-match_date')
    
    return render(request, 'referees/matches.html', {
        'referee': referee,
        'matches': matches
    })

@login_required
def view_report(request, report_id):
    """View submitted report"""
    report = get_object_or_404(MatchReport, id=report_id)
    
    # Check if user is the referee who submitted or admin
    if not (request.user.is_staff or report.referee.user == request.user):
        messages.error(request, 'You are not authorized to view this report.')
        return redirect('home')
    
    goals = Goal.objects.filter(match=report.match)
    cards = Card.objects.filter(match=report.match)
    
    return render(request, 'referees/view_report.html', {
        'report': report,
        'goals': goals,
        'cards': cards
    })