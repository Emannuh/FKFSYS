from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.db.models import Q, Sum
from datetime import timedelta
import random
import math

from .models import (
    Tournament,
    TournamentTeamRegistration,
    TournamentPlayerRegistration,
    TournamentGroup,
    TournamentGroupStanding,
    TournamentMatch,
    TournamentMatchOfficials,
    TournamentGoal,
    TournamentCard,
    ExternalTeam,
    ExternalPlayer,
)
from .forms import (
    TournamentForm,
    TeamRegistrationForm,
    TeamRegistrationReviewForm,
    PlayerRegistrationForm,
    TournamentMatchForm,
    MatchResultForm,
    ExternalTeamForm,
    ExternalPlayerForm,
    ImportLeagueTeamsForm,
    TournamentMatchOfficialsForm,
    GenerateFixturesForm,
)
from teams.models import Team, Player


# ── permission helpers ────────────────────────────────────────────────────
def admin_required(user):
    return user.is_superuser or user.groups.filter(name='League Admin').exists()


def team_manager_required(user):
    return user.groups.filter(name='Team Managers').exists() or user.is_superuser


# ══════════════════════════════════════════════════════════════════════════
#  PUBLIC VIEWS
# ══════════════════════════════════════════════════════════════════════════

def tournament_list(request):
    """Public listing of all non-draft tournaments."""
    tournaments = Tournament.objects.exclude(status='draft')
    context = {'tournaments': tournaments}
    return render(request, 'tournaments/tournament_list.html', context)


def tournament_detail(request, slug):
    """Public detail page for a tournament."""
    tournament = get_object_or_404(Tournament, slug=slug)
    registrations = tournament.registrations.filter(status='approved')
    groups = tournament.groups.prefetch_related('standings__team_registration__team')
    upcoming = tournament.matches.filter(status='scheduled').order_by('match_date')[:10]
    results = tournament.matches.filter(status='completed').order_by('-match_date')[:10]
    context = {
        'tournament': tournament,
        'registrations': registrations,
        'groups': groups,
        'upcoming': upcoming,
        'results': results,
    }
    return render(request, 'tournaments/tournament_detail.html', context)


def tournament_fixtures(request, slug):
    """All matches for a tournament."""
    tournament = get_object_or_404(Tournament, slug=slug)
    matches = tournament.matches.select_related(
        'home_team__team', 'away_team__team', 'group'
    ).order_by('match_date')
    context = {'tournament': tournament, 'matches': matches}
    return render(request, 'tournaments/tournament_fixtures.html', context)


def tournament_standings(request, slug):
    """Group standings for a tournament."""
    tournament = get_object_or_404(Tournament, slug=slug)
    groups = tournament.groups.prefetch_related(
        'standings__team_registration__team'
    ).order_by('name')
    context = {'tournament': tournament, 'groups': groups}
    return render(request, 'tournaments/tournament_standings.html', context)


# ══════════════════════════════════════════════════════════════════════════
#  ADMIN: TOURNAMENT CRUD
# ══════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def create_tournament(request):
    if request.method == 'POST':
        form = TournamentForm(request.POST, request.FILES)
        if form.is_valid():
            tournament = form.save(commit=False)
            tournament.created_by = request.user
            tournament.save()
            messages.success(request, f'✅ Tournament "{tournament.name}" created.')
            return redirect('tournaments:tournament_detail', slug=tournament.slug)
    else:
        form = TournamentForm()
    return render(request, 'tournaments/create_tournament.html', {'form': form})


@login_required
@user_passes_test(admin_required)
def edit_tournament(request, slug):
    tournament = get_object_or_404(Tournament, slug=slug)
    if request.method == 'POST':
        form = TournamentForm(request.POST, request.FILES, instance=tournament)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Tournament updated.')
            return redirect('tournaments:tournament_detail', slug=tournament.slug)
    else:
        form = TournamentForm(instance=tournament)
    return render(request, 'tournaments/edit_tournament.html', {'form': form, 'tournament': tournament})


@login_required
@user_passes_test(admin_required)
def delete_tournament(request, slug):
    tournament = get_object_or_404(Tournament, slug=slug)
    if request.method == 'POST':
        name = tournament.name
        tournament.delete()
        messages.success(request, f'🗑️ Tournament "{name}" deleted.')
        return redirect('tournaments:tournament_list')
    return render(request, 'tournaments/delete_tournament.html', {'tournament': tournament})


@login_required
@user_passes_test(admin_required)
def change_tournament_status(request, slug):
    """Quick status toggle from the admin panel."""
    tournament = get_object_or_404(Tournament, slug=slug)
    new_status = request.POST.get('status')
    valid = [c[0] for c in Tournament.STATUS_CHOICES]
    if new_status in valid:
        tournament.status = new_status
        tournament.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Status changed to {tournament.get_status_display()}.')
    return redirect('tournaments:tournament_detail', slug=tournament.slug)


# ══════════════════════════════════════════════════════════════════════════
#  TEAM REGISTRATION  (League teams – team manager self-registers)
# ══════════════════════════════════════════════════════════════════════════

@login_required
def register_team(request, slug):
    """Team manager registers their league team for a tournament."""
    tournament = get_object_or_404(Tournament, slug=slug)

    if not tournament.is_registration_open:
        messages.error(request, 'Registration is closed for this tournament.')
        return redirect('tournaments:tournament_detail', slug=slug)

    team = Team.objects.filter(manager=request.user, status='approved').first()
    if not team:
        messages.error(request, 'You must manage an approved team to register.')
        return redirect('tournaments:tournament_detail', slug=slug)

    if TournamentTeamRegistration.objects.filter(tournament=tournament, team=team).exists():
        messages.info(request, 'Your team is already registered for this tournament.')
        return redirect('tournaments:tournament_detail', slug=slug)

    if tournament.registrations.filter(status='approved').count() >= tournament.max_teams:
        messages.error(request, 'This tournament has reached maximum capacity.')
        return redirect('tournaments:tournament_detail', slug=slug)

    if request.method == 'POST':
        form = TeamRegistrationForm(request.POST)
        if form.is_valid():
            TournamentTeamRegistration.objects.create(
                tournament=tournament,
                team=team,
                team_type='league',
                registered_by=request.user,
            )
            messages.success(request, f'✅ {team.team_name} registered. Awaiting admin approval.')
            return redirect('tournaments:tournament_detail', slug=slug)
    else:
        form = TeamRegistrationForm()

    context = {'tournament': tournament, 'team': team, 'form': form}
    return render(request, 'tournaments/register_team.html', context)


# ══════════════════════════════════════════════════════════════════════════
#  EXTERNAL TEAM REGISTRATION  (teams NOT in the league)
# ══════════════════════════════════════════════════════════════════════════

def register_external_team(request, slug):
    """
    Public portal for external teams to register for a tournament.
    Creates an ExternalTeam + TournamentTeamRegistration.
    Optionally creates a user account for the team manager.
    """
    tournament = get_object_or_404(Tournament, slug=slug)

    if not tournament.allow_external_teams:
        messages.error(request, 'This tournament does not accept external teams.')
        return redirect('tournaments:tournament_detail', slug=slug)

    if not tournament.is_registration_open:
        messages.error(request, 'Registration is closed for this tournament.')
        return redirect('tournaments:tournament_detail', slug=slug)

    if tournament.registrations.filter(status='approved').count() >= tournament.max_teams:
        messages.error(request, 'This tournament has reached maximum capacity.')
        return redirect('tournaments:tournament_detail', slug=slug)

    if request.method == 'POST':
        form = ExternalTeamForm(request.POST, request.FILES)
        if form.is_valid():
            ext_team = form.save(commit=False)
            ext_team.tournament = tournament
            if request.user.is_authenticated:
                ext_team.manager_user = request.user
            ext_team.save()

            # Create tournament registration
            TournamentTeamRegistration.objects.create(
                tournament=tournament,
                external_team=ext_team,
                team_type='external',
                registered_by=request.user if request.user.is_authenticated else None,
            )
            messages.success(
                request,
                f'✅ {ext_team.team_name} registered for {tournament.name}. '
                f'Awaiting admin approval.'
            )
            return redirect('tournaments:tournament_detail', slug=slug)
    else:
        form = ExternalTeamForm()

    context = {'tournament': tournament, 'form': form}
    return render(request, 'tournaments/register_external_team.html', context)


# ══════════════════════════════════════════════════════════════════════════
#  IMPORT LEAGUE TEAMS  (admin bulk-imports existing teams)
# ══════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def import_league_teams(request, slug):
    """Admin selects existing league teams and auto-registers + approves them."""
    tournament = get_object_or_404(Tournament, slug=slug)

    if request.method == 'POST':
        form = ImportLeagueTeamsForm(request.POST, tournament=tournament)
        if form.is_valid():
            teams = form.cleaned_data['teams']
            created = 0
            for team in teams:
                _, was_created = TournamentTeamRegistration.objects.get_or_create(
                    tournament=tournament,
                    team=team,
                    defaults={
                        'team_type': 'league',
                        'registered_by': request.user,
                        'status': 'approved',  # auto-approved when admin imports
                        'payment_confirmed': True,
                    }
                )
                if was_created:
                    created += 1
            messages.success(request, f'✅ {created} league team(s) imported and approved.')
            return redirect('tournaments:manage_registrations', slug=slug)
    else:
        form = ImportLeagueTeamsForm(tournament=tournament)

    context = {'tournament': tournament, 'form': form}
    return render(request, 'tournaments/import_league_teams.html', context)


@login_required
@user_passes_test(admin_required)
def manage_registrations(request, slug):
    """Admin views & approves/rejects team registrations."""
    tournament = get_object_or_404(Tournament, slug=slug)
    registrations = tournament.registrations.select_related(
        'team', 'external_team'
    ).order_by('registered_at')
    context = {'tournament': tournament, 'registrations': registrations}
    return render(request, 'tournaments/manage_registrations.html', context)


@login_required
@user_passes_test(admin_required)
def review_registration(request, pk):
    reg = get_object_or_404(TournamentTeamRegistration, pk=pk)
    if request.method == 'POST':
        form = TeamRegistrationReviewForm(request.POST, instance=reg)
        if form.is_valid():
            form.save()
            messages.success(request, f'{reg.display_name} → {reg.get_status_display()}')
            return redirect('tournaments:manage_registrations', slug=reg.tournament.slug)
    else:
        form = TeamRegistrationReviewForm(instance=reg)
    context = {'form': form, 'reg': reg}
    return render(request, 'tournaments/review_registration.html', context)


# ══════════════════════════════════════════════════════════════════════════
#  PLAYER REGISTRATION — LEAGUE TEAMS (import from roster)
# ══════════════════════════════════════════════════════════════════════════

@login_required
def register_players(request, slug):
    """Team manager registers league players for their tournament squad."""
    tournament = get_object_or_404(Tournament, slug=slug)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    if not team:
        messages.error(request, 'You must manage an approved team.')
        return redirect('tournaments:tournament_detail', slug=slug)

    team_reg = TournamentTeamRegistration.objects.filter(
        tournament=tournament, team=team, status='approved'
    ).first()
    if not team_reg:
        messages.error(request, 'Your team must be approved for this tournament first.')
        return redirect('tournaments:tournament_detail', slug=slug)

    current_squad = TournamentPlayerRegistration.objects.filter(
        team_registration=team_reg
    ).select_related('player')

    if request.method == 'POST':
        form = PlayerRegistrationForm(request.POST, team=team, tournament=tournament)
        if form.is_valid():
            selected = form.cleaned_data['players']
            total_after = current_squad.count() + selected.count()
            if total_after > tournament.max_squad_size:
                messages.error(
                    request,
                    f'Max squad size is {tournament.max_squad_size}. '
                    f'You already have {current_squad.count()} players.'
                )
            else:
                for player in selected:
                    TournamentPlayerRegistration.objects.create(
                        tournament=tournament,
                        team_registration=team_reg,
                        player=player,
                        jersey_number=player.jersey_number,
                    )
                messages.success(request, f'✅ {selected.count()} player(s) added to squad.')
                return redirect('tournaments:register_players', slug=slug)
    else:
        form = PlayerRegistrationForm(team=team, tournament=tournament)

    context = {
        'tournament': tournament,
        'team': team,
        'team_reg': team_reg,
        'squad': current_squad,
        'form': form,
    }
    return render(request, 'tournaments/register_players.html', context)


# ══════════════════════════════════════════════════════════════════════════
#  PLAYER REGISTRATION — EXTERNAL TEAMS (add players manually)
# ══════════════════════════════════════════════════════════════════════════

@login_required
def register_external_players(request, slug, ext_team_pk):
    """
    Manager of an external team adds players one-by-one.
    Creates ExternalPlayer records + TournamentPlayerRegistration.
    """
    tournament = get_object_or_404(Tournament, slug=slug)
    ext_team = get_object_or_404(ExternalTeam, pk=ext_team_pk, tournament=tournament)

    team_reg = TournamentTeamRegistration.objects.filter(
        tournament=tournament, external_team=ext_team, status='approved'
    ).first()
    if not team_reg:
        messages.error(request, 'This team must be approved before adding players.')
        return redirect('tournaments:tournament_detail', slug=slug)

    current_squad = TournamentPlayerRegistration.objects.filter(
        team_registration=team_reg
    ).select_related('external_player')

    if request.method == 'POST':
        form = ExternalPlayerForm(request.POST, request.FILES)
        if form.is_valid():
            if current_squad.count() >= tournament.max_squad_size:
                messages.error(request, f'Squad is full ({tournament.max_squad_size} players max).')
            else:
                ext_player = form.save(commit=False)
                ext_player.external_team = ext_team
                ext_player.save()

                TournamentPlayerRegistration.objects.create(
                    tournament=tournament,
                    team_registration=team_reg,
                    external_player=ext_player,
                    jersey_number=ext_player.jersey_number,
                )
                messages.success(request, f'✅ {ext_player.full_name} added to squad.')
                return redirect(
                    'tournaments:register_external_players',
                    slug=slug, ext_team_pk=ext_team.pk,
                )
    else:
        form = ExternalPlayerForm()

    context = {
        'tournament': tournament,
        'ext_team': ext_team,
        'team_reg': team_reg,
        'squad': current_squad,
        'form': form,
    }
    return render(request, 'tournaments/register_external_players.html', context)


# ══════════════════════════════════════════════════════════════════════════
#  ADMIN: MATCHES
# ══════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def create_match(request, slug):
    tournament = get_object_or_404(Tournament, slug=slug)
    if request.method == 'POST':
        form = TournamentMatchForm(request.POST, tournament=tournament)
        if form.is_valid():
            match = form.save(commit=False)
            match.tournament = tournament
            match.save()
            messages.success(request, '✅ Match created.')
            return redirect('tournaments:tournament_fixtures', slug=slug)
    else:
        form = TournamentMatchForm(tournament=tournament)
    return render(request, 'tournaments/create_match.html', {'form': form, 'tournament': tournament})


@login_required
@user_passes_test(admin_required)
def record_result(request, match_pk):
    match = get_object_or_404(TournamentMatch, pk=match_pk)
    if request.method == 'POST':
        form = MatchResultForm(request.POST, instance=match)
        if form.is_valid():
            match = form.save(commit=False)
            match.status = 'completed'
            match.save()
            if match.group and match.home_team and match.away_team:
                _update_group_standing(match)
            messages.success(request, '✅ Result recorded.')
            return redirect('tournaments:tournament_fixtures', slug=match.tournament.slug)
    else:
        form = MatchResultForm(instance=match)
    return render(request, 'tournaments/record_result.html', {'form': form, 'match': match})


# ══════════════════════════════════════════════════════════════════════════
#  ADMIN: MATCH OFFICIALS APPOINTMENT
# ══════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
@login_required
@user_passes_test(admin_required)
def appoint_officials(request, match_pk):
    """Admin appoints referees to a tournament match."""
    match = get_object_or_404(TournamentMatch, pk=match_pk)
    officials, _ = TournamentMatchOfficials.objects.get_or_create(match=match)

    if request.method == 'POST':
        form = TournamentMatchOfficialsForm(request.POST, instance=officials)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.appointed_by = request.user
            obj.appointed_at = timezone.now()
            obj.status = 'APPOINTED'
            obj.save()
            messages.success(request, '✅ Officials appointed.')
            return redirect('tournaments:tournament_fixtures', slug=match.tournament.slug)
    else:
        form = TournamentMatchOfficialsForm(instance=officials)

    context = {'form': form, 'match': match, 'tournament': match.tournament}
    return render(request, 'tournaments/appoint_officials.html', context)


@login_required
@user_passes_test(admin_required)
def matches_needing_officials(request, slug):
    """List tournament matches without appointed officials."""
    tournament = get_object_or_404(Tournament, slug=slug)
    matches = tournament.matches.filter(
        Q(officials__isnull=True) | Q(officials__status='PENDING')
    ).select_related('home_team__team', 'home_team__external_team',
                     'away_team__team', 'away_team__external_team').order_by('match_date')
    context = {'tournament': tournament, 'matches': matches}
    return render(request, 'tournaments/matches_needing_officials.html', context)


# ══════════════════════════════════════════════════════════════════════════
#  ADMIN: AUTO-GENERATE FIXTURES
# ══════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def generate_fixtures(request, slug):
    """Auto-generate fixtures based on tournament format."""
    tournament = get_object_or_404(Tournament, slug=slug)
    approved_regs = list(
        tournament.registrations.filter(status='approved').select_related('team', 'external_team')
    )
    existing_match_count = tournament.matches.count()

    if len(approved_regs) < 2:
        messages.error(request, 'Need at least 2 approved teams to generate fixtures.')
        return redirect('tournaments:tournament_detail', slug=slug)

    if request.method == 'POST':
        form = GenerateFixturesForm(request.POST)
        if form.is_valid():
            # Delete existing fixtures if any
            if existing_match_count > 0:
                tournament.matches.all().delete()
                tournament.groups.all().delete()

            first_date = form.cleaned_data['first_match_date']
            interval = form.cleaned_data['days_between_rounds']
            venue = form.cleaned_data['venue'] or tournament.venue

            if tournament.format == 'knockout':
                _generate_knockout_fixtures(tournament, approved_regs, first_date, interval, venue)
            elif tournament.format == 'group_knockout':
                _generate_group_knockout_fixtures(tournament, approved_regs, first_date, interval, venue)
            elif tournament.format == 'round_robin':
                _generate_round_robin_fixtures(tournament, approved_regs, first_date, interval, venue)
            else:
                _generate_round_robin_fixtures(tournament, approved_regs, first_date, interval, venue)

            messages.success(request, f'✅ Fixtures generated for {tournament.name}!')
            return redirect('tournaments:tournament_fixtures', slug=slug)
    else:
        form = GenerateFixturesForm(initial={'venue': tournament.venue})

    context = {
        'tournament': tournament,
        'form': form,
        'team_count': len(approved_regs),
        'existing_match_count': existing_match_count,
    }
    return render(request, 'tournaments/generate_fixtures.html', context)


def _generate_knockout_fixtures(tournament, teams, first_date, interval, venue):
    """Generate single-elimination bracket."""
    random.shuffle(teams)
    n = len(teams)

    # Pad to next power of 2 for byes
    bracket_size = 1
    while bracket_size < n:
        bracket_size *= 2

    # Determine first round name
    stage_map = {
        2: 'final', 4: 'semi_final', 8: 'quarter_final',
        16: 'round_of_16', 32: 'round_of_32',
    }
    first_stage = stage_map.get(bracket_size, 'round_of_32')

    match_num = 1
    current_date = first_date

    for i in range(0, bracket_size, 2):
        home = teams[i] if i < n else None
        away = teams[i + 1] if (i + 1) < n else None

        if home and away:
            TournamentMatch.objects.create(
                tournament=tournament,
                stage=first_stage,
                match_number=match_num,
                home_team=home,
                away_team=away,
                match_date=current_date,
                venue=venue,
            )
        elif home and not away:
            # Bye – home team advances, create placeholder for next round
            pass
        match_num += 1

    # Create placeholder matches for subsequent rounds
    rounds_remaining = int(math.log2(bracket_size)) - 1
    stage_sequence = ['round_of_16', 'quarter_final', 'semi_final', 'final']
    # Find starting index in sequence
    try:
        idx = stage_sequence.index(first_stage) + 1
    except ValueError:
        idx = 0

    for r in range(rounds_remaining):
        current_date += timedelta(days=interval)
        stage = stage_sequence[idx + r] if (idx + r) < len(stage_sequence) else 'final'
        matches_in_round = bracket_size // (2 ** (r + 2))
        for m in range(matches_in_round):
            TournamentMatch.objects.create(
                tournament=tournament,
                stage=stage,
                match_number=match_num,
                match_date=current_date,
                venue=venue,
            )
            match_num += 1


def _generate_group_knockout_fixtures(tournament, teams, first_date, interval, venue):
    """Generate group stage fixtures + empty knockout placeholders."""
    random.shuffle(teams)
    group_count = tournament.group_count or 4

    # Distribute teams into groups
    groups = []
    for g in range(group_count):
        group_obj = TournamentGroup.objects.create(
            tournament=tournament,
            name=f"Group {chr(65 + g)}",  # A, B, C, …
        )
        groups.append(group_obj)

    for idx, team_reg in enumerate(teams):
        g = groups[idx % group_count]
        g.teams.add(team_reg)
        TournamentGroupStanding.objects.create(
            group=g, team_registration=team_reg,
        )

    # Generate round-robin fixtures within each group
    match_num = 1
    current_date = first_date

    for group_obj in groups:
        group_teams = list(group_obj.teams.all())
        n = len(group_teams)
        if n < 2:
            continue

        if n % 2 == 1:
            group_teams.append(None)
            n = len(group_teams)

        total_rounds = n - 1
        rd = 0
        for round_idx in range(total_rounds):
            round_date = current_date + timedelta(days=interval * rd)
            for i in range(n // 2):
                t1 = group_teams[i]
                t2 = group_teams[n - 1 - i]
                if t1 and t2:
                    TournamentMatch.objects.create(
                        tournament=tournament,
                        group=group_obj,
                        stage='group',
                        match_number=match_num,
                        home_team=t1,
                        away_team=t2,
                        match_date=round_date,
                        venue=venue,
                    )
                    match_num += 1
            # Rotate (keep first fixed)
            group_teams = [group_teams[0]] + [group_teams[-1]] + group_teams[1:-1]
            rd += 1

    # Determine knockout stage based on number of groups
    total_qualified = group_count * 2  # top 2 per group
    ko_stages = {2: ['final'], 4: ['semi_final', 'final'],
                 8: ['quarter_final', 'semi_final', 'final'],
                 16: ['round_of_16', 'quarter_final', 'semi_final', 'final']}
    stages = ko_stages.get(total_qualified, ['semi_final', 'final'])

    ko_date = current_date + timedelta(days=interval * (total_rounds + 1))
    matches_in_round = total_qualified // 2
    for stage_name in stages:
        for _ in range(matches_in_round):
            TournamentMatch.objects.create(
                tournament=tournament,
                stage=stage_name,
                match_number=match_num,
                match_date=ko_date,
                venue=venue,
            )
            match_num += 1
        matches_in_round //= 2
        ko_date += timedelta(days=interval)


def _generate_round_robin_fixtures(tournament, teams, first_date, interval, venue):
    """Generate single round-robin fixtures."""
    random.shuffle(teams)
    n = len(teams)
    team_list = list(teams)

    if n % 2 == 1:
        team_list.append(None)
        n = len(team_list)

    total_rounds = n - 1
    match_num = 1

    for round_idx in range(total_rounds):
        round_date = first_date + timedelta(days=interval * round_idx)
        for i in range(n // 2):
            t1 = team_list[i]
            t2 = team_list[n - 1 - i]
            if t1 and t2:
                TournamentMatch.objects.create(
                    tournament=tournament,
                    stage='group',
                    match_number=match_num,
                    home_team=t1,
                    away_team=t2,
                    match_date=round_date,
                    venue=venue,
                )
                match_num += 1
        # Rotate (keep first element fixed)
        team_list = [team_list[0]] + [team_list[-1]] + team_list[1:-1]


def _update_group_standing(match):
    """Recalculate group standing row for both teams after a result."""
    for team_reg in [match.home_team, match.away_team]:
        standing, _ = TournamentGroupStanding.objects.get_or_create(
            group=match.group, team_registration=team_reg,
        )
        team_matches = TournamentMatch.objects.filter(
            group=match.group, status='completed',
        ).filter(Q(home_team=team_reg) | Q(away_team=team_reg))

        w = d = l = gf = ga = 0
        for m in team_matches:
            if m.home_team == team_reg:
                sf, sa = m.home_score, m.away_score
            else:
                sf, sa = m.away_score, m.home_score
            gf += sf
            ga += sa
            if sf > sa:
                w += 1
            elif sf == sa:
                d += 1
            else:
                l += 1

        standing.played = w + d + l
        standing.won = w
        standing.drawn = d
        standing.lost = l
        standing.goals_for = gf
        standing.goals_against = ga
        standing.save()


# ══════════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD OVERVIEW
# ══════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(admin_required)
def admin_tournament_dashboard(request):
    """Central admin page listing all tournaments with quick stats."""
    tournaments = Tournament.objects.all()
    context = {'tournaments': tournaments}
    return render(request, 'tournaments/admin_dashboard.html', context)
