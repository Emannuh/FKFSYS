"""Public tournament pages (no login required)."""
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from ..access import is_tournament_admin
from ..models import Tournament, TournamentMatch, TournamentTeamRegistration

APPROVED = TournamentTeamRegistration.Status.APPROVED


def with_approved_count(qs):
    """Annotate ``approved_teams`` so list pages avoid a count query per row."""
    return qs.annotate(
        approved_teams=Count('registrations', filter=Q(registrations__status=APPROVED))
    )


def get_visible_tournament(request, slug) -> Tournament:
    """Drafts are only visible to tournament admins."""
    tournament = get_object_or_404(Tournament, slug=slug)
    if tournament.status == Tournament.Status.DRAFT and not is_tournament_admin(request.user):
        raise Http404
    return tournament


def _team_regs(qs):
    return qs.select_related('home_team__team', 'home_team__external_team',
                             'away_team__team', 'away_team__external_team')


def tournament_list(request):
    """Public listing of all non-draft tournaments."""
    tournaments = with_approved_count(Tournament.objects.exclude(status=Tournament.Status.DRAFT))
    return render(request, 'tournaments/tournament_list.html', {
        'tournaments': tournaments,
        'can_manage': is_tournament_admin(request.user),
    })


def tournament_detail(request, slug):
    tournament = get_visible_tournament(request, slug)
    matches = _team_regs(tournament.matches.all())
    return render(request, 'tournaments/tournament_detail.html', {
        'tournament': tournament,
        'registrations': tournament.registrations.filter(status=APPROVED)
                                   .select_related('team', 'external_team'),
        'upcoming': matches.filter(status=TournamentMatch.Status.SCHEDULED).order_by('match_date')[:10],
        'results': matches.filter(status=TournamentMatch.Status.COMPLETED).order_by('-match_date')[:10],
        'can_manage': is_tournament_admin(request.user),
    })


def tournament_fixtures(request, slug):
    tournament = get_visible_tournament(request, slug)
    matches = _team_regs(tournament.matches.select_related('group')).order_by('match_date', 'match_number')
    return render(request, 'tournaments/tournament_fixtures.html', {
        'tournament': tournament,
        'matches': matches,
        'can_manage': is_tournament_admin(request.user),
    })


def tournament_standings(request, slug):
    tournament = get_visible_tournament(request, slug)
    groups = tournament.groups.prefetch_related(
        'standings__team_registration__team',
        'standings__team_registration__external_team',
    ).order_by('name')
    return render(request, 'tournaments/tournament_standings.html', {
        'tournament': tournament, 'groups': groups,
    })
