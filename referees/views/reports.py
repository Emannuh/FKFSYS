"""Match reports: centre-referee submission and Referees Manager review."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from fkf_league.permissions import is_referees_manager
from matches.models import Match
from teams.models import Player

from .. import services
from ..forms import CautionForm, MatchGoalForm, MatchReportForm, MatchScoreForm
from ..models import (
    Caution, MatchdaySquad, MatchGoal, MatchReport, ReservePlayer, StartingLineup,
)
from ._common import current_referee, manager_required

logger = logging.getLogger(__name__)

EDITABLE_REPORT_STATES = (MatchReport.Status.DRAFT, MatchReport.Status.REJECTED)

GoalFormSet = inlineformset_factory(Match, MatchGoal, form=MatchGoalForm, extra=1, can_delete=True)
CardFormSet = inlineformset_factory(Match, Caution, form=CautionForm, extra=1, can_delete=True)
StartingLineupFormSet = inlineformset_factory(
    Match, StartingLineup, fields=['player', 'jersey_number', 'position', 'team'], extra=0, can_delete=True,
)
ReserveFormSet = inlineformset_factory(
    Match, ReservePlayer, fields=['player', 'jersey_number', 'team'], extra=0, can_delete=True,
)


def _restrict_players_to_team(formset, match) -> None:
    """Limit each lineup row's player choices to its team (bound data first, then instance)."""
    allowed = Player.objects.filter(team_id__in=[match.home_team_id, match.away_team_id])
    for i, form in enumerate(formset.forms):
        team_id = (form.data.get(f'{formset.prefix}-{i}-team') if form.is_bound else None) or form.instance.team_id
        form.fields['player'].queryset = allowed.filter(team_id=team_id) if team_id else allowed
        form.fields['team'].queryset = form.fields['team'].queryset.filter(
            pk__in=[match.home_team_id, match.away_team_id],
        )


def _seed_lineups_from_squads(match) -> None:
    """First visit: copy approved matchday squads into the report lineups."""
    if StartingLineup.objects.filter(match=match).exists():
        return
    for squad in MatchdaySquad.objects.filter(match=match, status=MatchdaySquad.Status.APPROVED):
        services.populate_lineup_from_squad(squad)


def _apply_score(request, match, score_form) -> None:
    services.record_result(match, score_form.cleaned_data['home_score'], score_form.cleaned_data['away_score'])


@login_required
@require_http_methods(['GET', 'POST'])
def submit_comprehensive_report(request, match_id):
    """
    Comprehensive report. Only the centre referee may create/edit it (while it is a
    draft or was rejected); other appointed officials and managers get read-only access.
    """
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    referee = current_referee(request.user)
    is_centre = services.is_centre_referee(referee, match)
    if not (is_centre or services.is_appointed_to(referee, match) or is_referees_manager(request.user)):
        raise PermissionDenied

    match_report = MatchReport.objects.filter(match=match).first()
    can_edit = is_centre and (match_report is None or match_report.status in EDITABLE_REPORT_STATES)
    if can_edit and match_report is None:
        match_report = MatchReport.objects.create(match=match, referee=referee)
    if can_edit:
        _seed_lineups_from_squads(match)
    report_instance = match_report or MatchReport(match=match)

    data = request.POST if request.method == 'POST' else None
    result_form = MatchReportForm(data, instance=report_instance)
    score_form = MatchScoreForm(data, instance=match)
    goal_formset = GoalFormSet(data, instance=match, form_kwargs={'match': match}, prefix='goal')
    card_formset = CardFormSet(data, instance=match, form_kwargs={'match': match}, prefix='card')
    starting_formset = StartingLineupFormSet(data, instance=match, prefix='starting')
    reserve_formset = ReserveFormSet(data, instance=match, prefix='reserve')
    _restrict_players_to_team(starting_formset, match)
    _restrict_players_to_team(reserve_formset, match)

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, "You are not allowed to edit this report.")
            return redirect('referees:referee_dashboard')

        if 'submit_score' in request.POST:
            if score_form.is_valid():
                _apply_score(request, match, score_form)
                messages.success(request, "Full-time score saved and league table updated.")
                return redirect('referees:submit_comprehensive_report', match_id=match.id)
            messages.error(request, "Please enter a valid full-time score.")
        else:
            parts = {
                'Report': result_form, 'Goals': goal_formset, 'Cautions': card_formset,
                'Starting lineup': starting_formset, 'Reserves': reserve_formset,
            }
            invalid = [name for name, part in parts.items() if not part.is_valid()]
            if not invalid:
                # Formsets update existing rows in place, so re-saving a draft never duplicates
                # goals/cards; Player tallies are adjusted by referees.goal_signals.
                with transaction.atomic():
                    report = result_form.save(commit=False)
                    if 'submit_report' in request.POST:
                        report.status = MatchReport.Status.SUBMITTED
                        report.submitted_at = timezone.now()
                    else:
                        report.status = MatchReport.Status.DRAFT
                        report.submitted_at = None
                    report.save()
                    for formset in (goal_formset, card_formset, starting_formset, reserve_formset):
                        formset.save()
                if report.status == MatchReport.Status.SUBMITTED:
                    messages.success(
                        request,
                        f"Comprehensive report submitted for {match.home_team} vs {match.away_team}. "
                        "Awaiting manager approval.",
                    )
                    return redirect('referees:referee_dashboard')
                messages.success(request, "Draft saved. You can continue adding entries.")
                return redirect('referees:submit_comprehensive_report', match_id=match.id)
            messages.error(request, f"Please correct the errors in: {', '.join(invalid)}.")

    def _empty(formset_cls, prefix, team):
        form = formset_cls.form(prefix=f'{prefix}-__prefix__')
        form.fields['player'].queryset = Player.objects.filter(team=team)
        return form

    context = {
        'match': match,
        'referee': referee,
        'confirmed': True,
        'result_form': result_form,
        'report_form': result_form,
        'score_form': score_form,
        'goal_formset': goal_formset,
        'card_formset': card_formset,
        'starting_formset': starting_formset,
        'reserve_formset': reserve_formset,
        'starting_empty_home': _empty(StartingLineupFormSet, 'starting', match.home_team),
        'starting_empty_away': _empty(StartingLineupFormSet, 'starting', match.away_team),
        'reserve_empty_home': _empty(ReserveFormSet, 'reserve', match.home_team),
        'reserve_empty_away': _empty(ReserveFormSet, 'reserve', match.away_team),
        'title': 'Submit Comprehensive Report',
        'can_edit': can_edit,
        'home_players': match.home_team.players.all(),
        'away_players': match.away_team.players.all(),
        'halftime_substitutions': match.substitutions.filter(minute__gte=45, minute__lte=60)
                                                     .select_related('player_in', 'player_out', 'team'),
    }
    return render(request, 'referees/match_report_comprehensive.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def submit_match_report(request, match_id):
    """Quick 'flash' report (score, goals, cautions) — centre referee only."""
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    referee = current_referee(request.user)
    officials = getattr(match, 'officials', None)
    if referee is None or officials is None or not services.is_centre_referee(referee, match):
        messages.error(request, "Only the appointed centre referee can submit the match report.")
        return redirect('referees:referee_dashboard')
    if not officials.main_confirmed:
        messages.error(request, "You need to confirm your appointment before submitting reports.")
        return redirect('referees:confirm_appointment', match_id=match.id)

    match_report, _ = MatchReport.objects.get_or_create(match=match, defaults={'referee': referee})
    if match_report.status not in EDITABLE_REPORT_STATES:
        messages.error(request, "This report has already been submitted and can no longer be edited.")
        return redirect('referees:referee_dashboard')

    data = request.POST if request.method == 'POST' else None
    result_form = MatchReportForm(data, instance=match_report)
    score_form = MatchScoreForm(data, instance=match)
    goal_formset = GoalFormSet(data, instance=match, prefix='matchgoal_set', form_kwargs={'match': match})
    card_formset = CardFormSet(data, instance=match, prefix='caution_set', form_kwargs={'match': match})

    if request.method == 'POST':
        if all(f.is_valid() for f in (result_form, score_form, goal_formset, card_formset)):
            with transaction.atomic():
                result_form.save()
                goal_formset.save()
                card_formset.save()
                _apply_score(request, match, score_form)
            messages.success(request, f"Flash Report submitted successfully for {match.home_team} vs {match.away_team}!")
            return redirect('referees:referee_dashboard')
        messages.error(request, "Please correct the errors in the form before submitting.")

    context = {
        'match': match,
        'referee': referee,
        'officials': officials,
        'result_form': result_form,
        'score_form': score_form,
        'goal_formset': goal_formset,
        'card_formset': card_formset,
        'can_edit': True,
        'title': 'Submit Flash Match Report',
        'home_players': match.home_team.players.all(),
        'away_players': match.away_team.players.all(),
    }
    return render(request, 'referees/flash_report.html', context)


@login_required
def view_report(request, report_id):
    """A referee's own report (staff/managers may view any)."""
    report = get_object_or_404(MatchReport.objects.select_related('match__home_team', 'match__away_team'), id=report_id)
    referee = current_referee(request.user)
    is_owner = referee is not None and report.referee_id == referee.pk
    if not (is_owner or is_referees_manager(request.user)):
        raise PermissionDenied
    context = {
        'report': report,
        'match': report.match,
        'title': f'Match Report #{report.id}',
        'referee': referee,
        'is_owner': is_owner,
    }
    return render(request, 'referees/view_report.html', context)


# ------------------------------------------------------------- manager review
@manager_required
def pending_reports(request):
    base = MatchReport.objects.select_related('match__home_team', 'match__away_team', 'referee', 'approved_by')
    pending = base.filter(status=MatchReport.Status.SUBMITTED)
    approved = base.filter(status=MatchReport.Status.APPROVED)
    rejected = base.filter(status=MatchReport.Status.REJECTED)
    context = {
        'pending_reports': pending,
        'approved_reports': approved,
        'rejected_reports': rejected,
        'pending_count': pending.count(),
        'approved_count': approved.count(),
        'rejected_count': rejected.count(),
        'title': 'Pending Match Reports',
    }
    return render(request, 'referees/manager/pending_reports.html', context)


def _review_report(request, report_id, *, approve: bool):
    report = get_object_or_404(MatchReport.objects.select_related('match'), id=report_id)
    template = 'referees/manager/approve_report.html' if approve else 'referees/manager/reject_report.html'
    if request.method == 'POST':
        if report.status != MatchReport.Status.SUBMITTED:
            messages.error(request, "Only submitted reports can be reviewed.")
            return redirect('referees:pending_reports')
        report.approved_by = request.user
        report.approved_at = timezone.now()
        if approve:
            report.status = MatchReport.Status.APPROVED
            report.rejection_reason = ''
            messages.success(request, f"Report for {report.match} has been approved!")
        else:
            report.status = MatchReport.Status.REJECTED
            report.rejection_reason = request.POST.get('rejection_reason', '').strip()
            messages.info(request, f"Report for {report.match} has been rejected and returned to the referee.")
        report.save()
        return redirect('referees:pending_reports')
    verb = 'Approve' if approve else 'Reject'
    return render(request, template, {'report': report, 'match': report.match, 'title': f'{verb} Report - {report.match}'})


@manager_required
def approve_report(request, report_id):
    return _review_report(request, report_id, approve=True)


@manager_required
def reject_report(request, report_id):
    return _review_report(request, report_id, approve=False)


@login_required
def report_detail_view(request, report_id):
    report = get_object_or_404(
        MatchReport.objects.select_related('match__home_team', 'match__away_team', 'referee'), id=report_id,
    )
    referee = current_referee(request.user)
    is_manager = is_referees_manager(request.user)
    is_referee = referee is not None and report.referee_id == referee.pk
    if not (is_manager or is_referee):
        raise PermissionDenied
    match = report.match
    context = {
        'report': report,
        'match': match,
        'goals': match.match_goals.select_related('player', 'team', 'assist_by'),
        'cautions': match.cautions.select_related('player', 'team'),
        'is_manager': is_manager,
        'is_referee': is_referee,
        'title': f'Report - {match}',
    }
    return render(request, 'referees/manager/report_detail.html', context)
