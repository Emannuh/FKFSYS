"""Admin-side tournament management: CRUD, registrations, matches,
results, fixture generation and officials appointment."""
import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..access import officials_manager_required, tournament_admin_required
from ..forms import (
    GenerateFixturesForm,
    ImportLeagueTeamsForm,
    MatchResultForm,
    TeamRegistrationReviewForm,
    TournamentForm,
    TournamentMatchEditForm,
    TournamentMatchForm,
    TournamentMatchOfficialsForm,
)
from ..models import Tournament, TournamentMatch, TournamentMatchOfficials, TournamentTeamRegistration
from ..services import FixtureGenerationError, generate_fixtures as build_fixtures
from ..services import recompute_group_standings, record_match_result
from .public import with_approved_count

logger = logging.getLogger(__name__)

APPROVED = TournamentTeamRegistration.Status.APPROVED


# ── Tournament CRUD ────────────────────────────────────────────────────────
@tournament_admin_required
def admin_tournament_dashboard(request):
    """Central admin page listing all tournaments with quick stats."""
    tournaments = list(with_approved_count(Tournament.objects.all()))
    # Stat-tile counts (the template's {% with %} counters could not accumulate and always showed 0).
    statuses = [t.status for t in tournaments]
    return render(request, 'tournaments/admin_dashboard.html', {
        'tournaments': tournaments,
        'active_count': sum(s in ('ongoing', 'registration') for s in statuses),
        'registration_count': statuses.count('registration'),
        'completed_count': statuses.count('completed'),
    })


@tournament_admin_required
def create_tournament(request):
    form = TournamentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        tournament = form.save(commit=False)
        tournament.created_by = request.user
        tournament.save()
        logger.info('Tournament created: id=%s user=%s', tournament.pk, request.user.pk)
        messages.success(request, f'Tournament "{tournament.name}" created.')
        return redirect('tournaments:tournament_detail', slug=tournament.slug)
    return render(request, 'tournaments/create_tournament.html', {'form': form})


@tournament_admin_required
def edit_tournament(request, slug):
    tournament = get_object_or_404(Tournament, slug=slug)
    form = TournamentForm(request.POST or None, request.FILES or None, instance=tournament)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tournament updated.')
        return redirect('tournaments:tournament_detail', slug=tournament.slug)
    return render(request, 'tournaments/edit_tournament.html', {'form': form, 'tournament': tournament})


@tournament_admin_required
def delete_tournament(request, slug):
    """GET shows a confirmation page; only POST deletes."""
    tournament = get_object_or_404(Tournament, slug=slug)
    if request.method == 'POST':
        name = tournament.name
        logger.info('Tournament deleted: id=%s user=%s', tournament.pk, request.user.pk)
        tournament.delete()
        messages.success(request, f'Tournament "{name}" deleted.')
        return redirect('tournaments:tournament_list')
    return render(request, 'tournaments/delete_tournament.html', {'tournament': tournament})


@tournament_admin_required
@require_POST
def change_tournament_status(request, slug):
    """Quick status toggle from the detail / edit pages."""
    tournament = get_object_or_404(Tournament, slug=slug)
    new_status = request.POST.get('status')
    if new_status in Tournament.Status.values:
        tournament.status = new_status
        tournament.save(update_fields=['status', 'updated_at'])
        logger.info('Tournament status: id=%s status=%s user=%s', tournament.pk, new_status, request.user.pk)
        messages.success(request, f'Status changed to {tournament.get_status_display()}.')
    else:
        messages.error(request, 'Invalid status.')
    return redirect('tournaments:tournament_detail', slug=tournament.slug)


# ── Registrations ──────────────────────────────────────────────────────────
@tournament_admin_required
def import_league_teams(request, slug):
    """Admin selects existing league teams and auto-registers + approves them."""
    tournament = get_object_or_404(Tournament, slug=slug)
    form = ImportLeagueTeamsForm(request.POST or None, tournament=tournament)
    if request.method == 'POST' and form.is_valid():
        created = 0
        with transaction.atomic():
            for team in form.cleaned_data['teams']:
                _, was_created = TournamentTeamRegistration.objects.get_or_create(
                    tournament=tournament, team=team,
                    defaults={
                        'team_type': TournamentTeamRegistration.TeamType.LEAGUE,
                        'registered_by': request.user,
                        'status': APPROVED,  # auto-approved when admin imports
                        'payment_confirmed': True,
                    },
                )
                created += was_created
        logger.info('League teams imported: tournament=%s count=%d user=%s', tournament.pk, created, request.user.pk)
        messages.success(request, f'{created} league team(s) imported and approved.')
        return redirect('tournaments:manage_registrations', slug=slug)
    return render(request, 'tournaments/import_league_teams.html', {'tournament': tournament, 'form': form})


@tournament_admin_required
def manage_registrations(request, slug):
    tournament = get_object_or_404(Tournament, slug=slug)
    registrations = tournament.registrations.select_related('team', 'external_team').order_by('registered_at')
    return render(request, 'tournaments/manage_registrations.html', {
        'tournament': tournament, 'registrations': registrations,
    })


@tournament_admin_required
def review_registration(request, pk):
    reg = get_object_or_404(
        TournamentTeamRegistration.objects.select_related('tournament', 'team', 'external_team'), pk=pk,
    )
    form = TeamRegistrationReviewForm(request.POST or None, instance=reg)
    if request.method == 'POST' and form.is_valid():
        form.save()
        logger.info('Registration reviewed: id=%s status=%s user=%s', reg.pk, reg.status, request.user.pk)
        messages.success(request, f'{reg.display_name} → {reg.get_status_display()}')
        return redirect('tournaments:manage_registrations', slug=reg.tournament.slug)
    return render(request, 'tournaments/review_registration.html', {'form': form, 'reg': reg})


# ── Matches & results ──────────────────────────────────────────────────────
@tournament_admin_required
def create_match(request, slug):
    tournament = get_object_or_404(Tournament, slug=slug)
    form = TournamentMatchForm(request.POST or None, tournament=tournament,
                               instance=TournamentMatch(tournament=tournament))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Match created.')
        return redirect('tournaments:tournament_fixtures', slug=slug)
    return render(request, 'tournaments/create_match.html', {'form': form, 'tournament': tournament})


@tournament_admin_required
def edit_tournament_match(request, match_pk):
    """Admin edits match time, venue, duration and TBD team slots."""
    match = get_object_or_404(TournamentMatch.objects.select_related('tournament', 'group'), pk=match_pk)
    form = TournamentMatchEditForm(request.POST or None, instance=match)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            match = form.save()
            teams_changed = {'home_team', 'away_team'} & set(form.changed_data)
            if match.group_id and teams_changed:
                recompute_group_standings(match.group)
        messages.success(request, f'Match #{match.match_number} updated.')
        return redirect('tournaments:tournament_fixtures', slug=match.tournament.slug)
    return render(request, 'tournaments/edit_tournament_match.html', {
        'form': form, 'match': match, 'tournament': match.tournament,
    })


@tournament_admin_required
def record_result(request, match_pk):
    match = get_object_or_404(
        TournamentMatch.objects.select_related('tournament', 'group', 'home_team', 'away_team'), pk=match_pk,
    )
    if not (match.home_team_id and match.away_team_id):
        messages.error(request, 'Both teams must be set before a result can be recorded.')
        return redirect('tournaments:tournament_fixtures', slug=match.tournament.slug)
    form = MatchResultForm(request.POST or None, instance=match)
    if request.method == 'POST' and form.is_valid():
        record_match_result(form.save(commit=False))
        logger.info('Result recorded: match=%s %s-%s user=%s',
                    match.pk, match.home_score, match.away_score, request.user.pk)
        messages.success(request, 'Result recorded.')
        return redirect('tournaments:tournament_fixtures', slug=match.tournament.slug)
    return render(request, 'tournaments/record_result.html', {'form': form, 'match': match})


@tournament_admin_required
def generate_fixtures(request, slug):
    """Auto-generate fixtures based on tournament format."""
    tournament = get_object_or_404(Tournament, slug=slug)
    team_count = tournament.registrations.filter(status=APPROVED).count()
    existing = tournament.matches.count()
    form = GenerateFixturesForm(request.POST or None, existing_matches=existing,
                                initial={'venue': tournament.venue})
    if request.method == 'POST' and form.is_valid():
        try:
            created = build_fixtures(
                tournament,
                first_date=form.cleaned_data['first_match_date'],
                interval_days=form.cleaned_data['days_between_rounds'],
                venue=form.cleaned_data['venue'],
                user=request.user,
            )
        except FixtureGenerationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'{created} fixtures generated for {tournament.name}.')
            return redirect('tournaments:tournament_fixtures', slug=slug)
    return render(request, 'tournaments/generate_fixtures.html', {
        'tournament': tournament,
        'form': form,
        'team_count': team_count,
        'existing_match_count': existing,
    })


# ── Officials ──────────────────────────────────────────────────────────────
@officials_manager_required
def appoint_officials(request, match_pk):
    """Admin / Referees Manager appoints referees to a tournament match."""
    match = get_object_or_404(TournamentMatch.objects.select_related('tournament'), pk=match_pk)
    officials = TournamentMatchOfficials.objects.filter(match=match).first() \
        or TournamentMatchOfficials(match=match)
    form = TournamentMatchOfficialsForm(request.POST or None, instance=officials)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.appointed_by = request.user
        obj.appointed_at = timezone.now()
        obj.status = TournamentMatchOfficials.Status.APPOINTED
        obj.save()
        logger.info('Tournament officials appointed: match=%s user=%s', match.pk, request.user.pk)
        messages.success(request, 'Officials appointed.')
        return redirect('tournaments:tournament_fixtures', slug=match.tournament.slug)
    return render(request, 'tournaments/appoint_officials.html', {
        'form': form, 'match': match, 'tournament': match.tournament,
    })


@officials_manager_required
def matches_needing_officials(request, slug):
    tournament = get_object_or_404(Tournament, slug=slug)
    matches = tournament.matches.filter(
        Q(officials__isnull=True) | Q(officials__status=TournamentMatchOfficials.Status.PENDING)
    ).select_related('home_team__team', 'home_team__external_team',
                     'away_team__team', 'away_team__external_team').order_by('match_date')
    return render(request, 'tournaments/matches_needing_officials.html', {
        'tournament': tournament, 'matches': matches,
    })
