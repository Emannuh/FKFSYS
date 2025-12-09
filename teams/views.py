from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Team, Player, Zone
from .forms import TeamRegistrationForm, PlayerRegistrationForm
from payments.models import Payment

def team_registration(request):
    if request.method == 'POST':
        form = TeamRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            team = form.save(commit=False)
            team.status = 'pending'
            team.save()
            
            # Store team ID in session for player registration
            request.session['team_id'] = team.id
            
            messages.success(request, 'Team registered successfully! Please add players.')
            return redirect('add_players')
    else:
        form = TeamRegistrationForm()
    
    return render(request, 'teams/register.html', {'form': form})

def add_players(request):
    team_id = request.session.get('team_id')
    if not team_id:
        return redirect('team_registration')
    
    team = get_object_or_404(Team, id=team_id)
    
    if request.method == 'POST':
        form = PlayerRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            player = form.save(commit=False)
            player.team = team
            
            # Check if jersey number is unique for this team
            if Player.objects.filter(team=team, jersey_number=player.jersey_number).exists():
                messages.error(request, f'Jersey number {player.jersey_number} is already taken.')
            else:
                player.save()
                messages.success(request, f'Player {player.full_name} added successfully!')
                
                # Check if we should add more players
                if 'add_more' in request.POST:
                    form = PlayerRegistrationForm()
                else:
                    return redirect('payment_page', team_id=team.id)
    else:
        form = PlayerRegistrationForm()
    
    players = Player.objects.filter(team=team)
    return render(request, 'teams/add_players.html', {
        'form': form,
        'team': team,
        'players': players
    })

def team_dashboard(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    players = Player.objects.filter(team=team)
    payments = Payment.objects.filter(team=team)
    
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
          players = Player.objects.filter(team=team)
    
    return render(request, 'teams/team_detail.html', {
        'team': team,
        'players': players
    })
def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    players = Player.objects.filter(team=team)

    return render(request, 'teams/team_detail.html', {
        'team': team,
        'players': players
    })  