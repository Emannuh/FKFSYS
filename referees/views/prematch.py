"""Pre-match meeting form: centre referee fills it in, League Admin then Referees Manager approve."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from fkf_league.permissions import is_league_admin, is_referees_manager
from matches.models import Match

from ..forms import PreMatchMeetingFormForm
from ..models import PreMatchMeetingForm
from ._common import current_referee, league_admin_required, manager_required

FORM_WINDOW = timedelta(hours=36)

_OFFICIAL_PREFIXES = (
    ('match_commissioner', 'match_commissioner'),
    ('main_referee', 'centre_referee'),
    ('assistant_1', 'asst1_referee'),
    ('assistant_2', 'asst2_referee'),
    ('fourth_official', 'fourth_official'),
)


def _autofill(prematch: PreMatchMeetingForm, match) -> None:
    """Copy fixture, officials and kit colours onto the form (server-side source of truth)."""
    prematch.match_date = timezone.localdate(match.match_date)
    prematch.home_team = match.home_team.team_name
    prematch.away_team = match.away_team.team_name
    prematch.venue = match.venue or ''
    officials = getattr(match, 'officials', None)
    if officials:
        for field, prefix in _OFFICIAL_PREFIXES:
            official = getattr(officials, field)
            if official:
                setattr(prematch, f'{prefix}_name', official.full_name)
                setattr(prematch, f'{prefix}_license', official.fkf_number)
                setattr(prematch, f'{prefix}_mobile', official.phone_number)
    prematch.home_gk_shirt_color = match.home_team.gk_home_jersey_color
    prematch.home_official_shirt = match.home_team.home_jersey_color
    prematch.away_gk_shirt_color = match.away_team.gk_away_jersey_color
    prematch.away_official_shirt = match.away_team.away_jersey_color


@login_required
@require_http_methods(['GET', 'POST'])
def submit_prematch_form(request, match_id):
    """Main referee only, within 36 hours before kick-off."""
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    referee = current_referee(request.user)
    officials = getattr(match, 'officials', None)
    if referee is None:
        messages.error(request, "You don't have a referee profile.")
        return redirect('referees:referee_dashboard')
    if officials is None:
        messages.error(request, "No officials have been appointed for this match yet.")
        return redirect('referees:referee_dashboard')
    if officials.main_referee_id != referee.pk:
        messages.error(request, "Only the main referee can submit the pre-match meeting form.")
        return redirect('referees:referee_dashboard')

    time_until_match = match.match_date - timezone.now()
    if time_until_match > FORM_WINDOW:
        hours = int(time_until_match.total_seconds() // 3600)
        messages.warning(request, f"Pre-match form can only be filled within 36 hours of the match. {hours} hours remaining.")
        return redirect('referees:referee_dashboard')
    if time_until_match.total_seconds() <= 0:
        messages.error(request, "Cannot fill pre-match form after the match has started.")
        return redirect('referees:referee_dashboard')

    prematch = PreMatchMeetingForm.objects.filter(match=match).first()
    if prematch is None:
        prematch = PreMatchMeetingForm(match=match, referee=referee, match_number=str(match.id))
        _autofill(prematch, match)
        prematch.save()

    if prematch.is_locked or prematch.status not in (PreMatchMeetingForm.Status.PENDING, PreMatchMeetingForm.Status.REJECTED):
        messages.error(request, "This form has been submitted and can no longer be edited.")
        return redirect('referees:view_prematch_form', form_id=prematch.id)

    if request.method == 'POST':
        form = PreMatchMeetingFormForm(request.POST, instance=prematch)
        if form.is_valid():
            prematch = form.save(commit=False)
            _autofill(prematch, match)
            if 'submit' in request.POST:
                prematch.status = PreMatchMeetingForm.Status.SUBMITTED
                prematch.submitted_at = timezone.now()
                messages.success(request, "Pre-Match Meeting Form submitted. Awaiting admin approval.")
            else:
                prematch.status = PreMatchMeetingForm.Status.PENDING
                messages.success(request, "Pre-Match Form saved as draft.")
            prematch.save()
            return redirect('referees:referee_dashboard')
    else:
        if not prematch.submitted_at:
            _autofill(prematch, match)
        form = PreMatchMeetingFormForm(instance=prematch)

    context = {'form': form, 'match': match, 'prematch_form': prematch, 'is_locked': prematch.is_locked}
    return render(request, 'referees/submit_prematch_form.html', context)


@login_required
def view_prematch_form(request, form_id):
    prematch = get_object_or_404(PreMatchMeetingForm.objects.select_related('match__officials'), id=form_id)
    referee = current_referee(request.user)
    officials = getattr(prematch.match, 'officials', None)
    is_main_referee = bool(referee and officials and officials.main_referee_id == referee.pk)
    is_manager = is_referees_manager(request.user)
    is_admin = is_league_admin(request.user)
    if not (is_main_referee or is_manager or is_admin):
        raise PermissionDenied
    context = {
        'prematch_form': prematch,
        'match': prematch.match,
        'is_main_referee': is_main_referee,
        'is_manager': is_manager,
        'is_admin': is_admin,
    }
    return render(request, 'referees/view_prematch_form.html', context)


def _review(request, form_id, *, expected_status, approve_status, stage: str, template: str):
    prematch = get_object_or_404(PreMatchMeetingForm.objects.select_related('match'), id=form_id)
    if prematch.status != expected_status:
        messages.error(request, f"This form is not awaiting {stage} approval.")
        return redirect('referees:view_prematch_form', form_id=form_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            prematch.status = approve_status
            setattr(prematch, f'{stage}_approved_at', timezone.now())
            setattr(prematch, f'{stage}_approved_by', request.user)
            messages.success(request, f"Pre-match form approved ({stage}).")
        elif action == 'reject':
            prematch.status = PreMatchMeetingForm.Status.REJECTED
            setattr(prematch, f'{stage}_rejection_reason', request.POST.get('rejection_reason', '').strip())
            messages.success(request, "Pre-match form rejected.")
        else:
            messages.error(request, "Unknown action.")
            return redirect('referees:view_prematch_form', form_id=form_id)
        prematch.save()
        return redirect('referees:view_prematch_form', form_id=form_id)

    return render(request, template, {'prematch_form': prematch, 'match': prematch.match})


@login_required
@permission_required('referees.approve_prematch_form_admin', raise_exception=True)
def admin_approve_prematch_form(request, form_id):
    return _review(
        request, form_id,
        expected_status=PreMatchMeetingForm.Status.SUBMITTED,
        approve_status=PreMatchMeetingForm.Status.ADMIN_APPROVED,
        stage='admin', template='referees/admin_approve_prematch_form.html',
    )


@login_required
@permission_required('referees.approve_prematch_form_manager', raise_exception=True)
def manager_approve_prematch_form(request, form_id):
    return _review(
        request, form_id,
        expected_status=PreMatchMeetingForm.Status.ADMIN_APPROVED,
        approve_status=PreMatchMeetingForm.Status.APPROVED,
        stage='manager', template='referees/manager_approve_prematch_form.html',
    )


@league_admin_required
def pending_prematch_forms_admin(request):
    forms = (
        PreMatchMeetingForm.objects.filter(status=PreMatchMeetingForm.Status.SUBMITTED)
        .select_related('match__home_team', 'match__away_team', 'referee')
        .order_by('-match__match_date')
    )
    return render(request, 'referees/pending_prematch_forms_admin.html', {'forms': forms})


@manager_required
def pending_prematch_forms_manager(request):
    forms = (
        PreMatchMeetingForm.objects.filter(status=PreMatchMeetingForm.Status.ADMIN_APPROVED)
        .select_related('match__home_team', 'match__away_team', 'referee')
        .order_by('-match__match_date')
    )
    return render(request, 'referees/pending_prematch_forms_manager.html', {'forms': forms})
