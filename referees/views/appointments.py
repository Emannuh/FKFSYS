"""Referee dashboard, appointment confirmation and the Referees Manager appointment tools."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from fkf_league.permissions import is_referee
from matches.models import Match
from tournaments.models import TournamentMatch, TournamentMatchOfficials

from .. import services
from ..forms import MatchOfficialsAppointmentForm
from ..models import (
    OFFICIAL_ROLES_BY_CODE, MatchOfficials, MatchReport, Referee, RefereeAvailability,
    SquadEditRequest,
)
from ._common import current_referee

logger = logging.getLogger(__name__)

APPOINTMENT_WINDOW_DAYS = 4
_REFEREE_RELATED = (
    'main_referee__user', 'assistant_1__user', 'assistant_2__user', 'fourth_official__user',
    'reserve_referee__user', 'var__user', 'avar1__user', 'match_commissioner__user',
)


def _display_name(official) -> str | None:
    if not official:
        return None
    if official.user_id and official.user.get_full_name():
        return official.user.get_full_name()
    return official.full_name


def _dashboard_role(code: str) -> str:
    """Role codes as the dashboard template expects them."""
    return {'FOURTH': 'RESERVE', 'RESERVE_AR': 'RESERVE'}.get(code, code)


# ------------------------------------------------------------- referee dashboard
@login_required
def referee_dashboard(request):
    """Dashboard for approved referees."""
    if request.user.groups.filter(name='Referees Manager').exists():
        return redirect('referees:matches_needing_officials')
    if not is_referee(request.user):
        messages.error(request, "Access denied. You are not registered as a referee.")
        return redirect('frontend:home')

    referee = current_referee(request.user)
    if referee is None:
        messages.error(request, "You need to register as a referee first.")
        return redirect('referees:referee_registration')
    if not referee.can_be_appointed():
        messages.warning(
            request, f"Your referee account is not active. Status: {referee.get_status_display()}",
        )
        return redirect('frontend:home')

    today = timezone.localdate()
    appointments = (
        services.appointments_for(referee)
        .select_related('match__home_team', 'match__away_team', 'match__zone', *_REFEREE_RELATED)
        .order_by('match__match_date')
    )

    upcoming_matches, pending_confirmation, current_matches, completed_matches = [], [], [], []
    for appointment in appointments:
        match = appointment.match
        role = appointment.role_of(referee)
        confirmed = appointment.is_confirmed(role)
        match_date = timezone.localdate(match.match_date)
        info = {
            'match': match,
            'role': _dashboard_role(role.code),
            'confirmed': confirmed,
            'appointment': appointment,
            'officials_data': {
                'main_referee': _display_name(appointment.main_referee),
                'assistant_1': _display_name(appointment.assistant_1),
                'assistant_2': _display_name(appointment.assistant_2),
                'reserve_referee': _display_name(appointment.fourth_official or appointment.reserve_referee),
                'var': _display_name(appointment.var),
                'avar1': _display_name(appointment.avar1),
                'match_commissioner': _display_name(appointment.match_commissioner),
            },
            'match_date': match_date,
            'can_confirm': match_date >= today and not confirmed,
        }
        if match_date < today:
            completed_matches.append(info)
        elif not confirmed:
            pending_confirmation.append(info)
            if match_date == today:
                current_matches.append(info)
        else:
            upcoming_matches.append(info)

    reports = MatchReport.objects.filter(referee=referee).select_related('match__home_team', 'match__away_team')
    draft_reports = reports.filter(status=MatchReport.Status.DRAFT)

    t_appointments = TournamentMatchOfficials.objects.filter(
        Q(main_referee=referee) | Q(assistant_1=referee) | Q(assistant_2=referee)
        | Q(fourth_official=referee) | Q(match_commissioner=referee)
    ).select_related(
        'match__tournament',
        'match__home_team__team', 'match__home_team__external_team',
        'match__away_team__team', 'match__away_team__external_team',
        'main_referee__user', 'assistant_1__user', 'assistant_2__user',
        'fourth_official__user', 'match_commissioner__user',
    ).order_by('match__match_date')

    tournament_upcoming, tournament_completed = [], []
    for t_appt in t_appointments:
        t_match = t_appt.match
        t_role = next(
            (code for code, field in (
                ('REFEREE', 'main_referee_id'), ('AR1', 'assistant_1_id'), ('AR2', 'assistant_2_id'),
                ('RESERVE', 'fourth_official_id'), ('COMMISSIONER', 'match_commissioner_id'),
            ) if getattr(t_appt, field) == referee.pk),
            'Unknown',
        )
        t_date = timezone.localdate(t_match.match_date) if t_match.match_date else None
        t_info = {
            'match': t_match,
            'role': t_role,
            'appointment': t_appt,
            'officials_data': {
                'main_referee': _display_name(t_appt.main_referee),
                'assistant_1': _display_name(t_appt.assistant_1),
                'assistant_2': _display_name(t_appt.assistant_2),
                'fourth_official': _display_name(t_appt.fourth_official),
                'match_commissioner': _display_name(t_appt.match_commissioner),
            },
            'match_date': t_date,
            'home_name': t_match.home_team.display_name if t_match.home_team else 'TBD',
            'away_name': t_match.away_team.display_name if t_match.away_team else 'TBD',
            'tournament_name': t_match.tournament.name,
            'tournament_slug': t_match.tournament.slug,
        }
        (tournament_upcoming if t_date and t_date >= today else tournament_completed).append(t_info)

    context = {
        'referee': referee,
        'current_matches': current_matches,
        'upcoming_matches': upcoming_matches,
        'pending_confirmation': pending_confirmation,
        'completed_matches': completed_matches,
        'pending_reports': draft_reports.order_by('-created_at')[:5],
        'submitted_reports': reports.filter(status=MatchReport.Status.SUBMITTED),
        'draft_reports': draft_reports,
        'pending_edit_requests': SquadEditRequest.objects.filter(
            squad__match__in=appointments.values('match'), status=SquadEditRequest.Status.PENDING,
        ).select_related('squad__match', 'squad__team'),
        'can_confirm': request.user.has_perm('referees.confirm_appointment'),
        'can_submit_report': request.user.has_perm('referees.submit_match_report'),
        'is_suspended': referee.status == Referee.Status.SUSPENDED,
        'suspension_reason': referee.suspension_reason if referee.status == Referee.Status.SUSPENDED else None,
        'total_appointments': len(appointments),
        'is_manager': False,
        'tournament_upcoming': tournament_upcoming,
        'tournament_completed': tournament_completed,
    }
    return render(request, 'referees/dashboard.html', context)


def _referee_and_role(request, match_id):
    """Resolve (match, officials, role) for the requesting referee, or a redirect response."""
    referee = current_referee(request.user)
    if referee is None:
        messages.error(request, "You need a referee profile to respond to appointments.")
        return None, redirect('referees:referee_registration')
    if not referee.can_be_appointed():
        messages.error(request, "Your account is not approved or active.")
        return None, redirect('referees:referee_dashboard')
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    officials = getattr(match, 'officials', None)
    role = officials.role_of(referee) if officials else None
    if role is None:
        messages.error(request, "You are not appointed to this match.")
        return None, redirect('referees:referee_dashboard')
    return (match, officials, role), None


@login_required
@permission_required('referees.confirm_appointment', raise_exception=True)
def confirm_appointment(request, match_id):
    resolved, response = _referee_and_role(request, match_id)
    if response:
        return response
    match, officials, role = resolved

    if request.method == 'POST':
        officials.mark_confirmed(role)
        officials.save(validate=False)
        messages.success(request, f"{role.label} appointment confirmed!")
        return redirect('referees:referee_dashboard')

    context = {
        'match': match,
        'officials': officials,
        'role': role.code,
        'already_confirmed': officials.is_confirmed(role),
        'role_display': role.label,
        'match_date': timezone.localdate(match.match_date),
        'today': timezone.localdate(),
    }
    return render(request, 'referees/confirm_appointment.html', context)


@login_required
@permission_required('referees.confirm_appointment', raise_exception=True)
def decline_appointment(request, match_id):
    resolved, response = _referee_and_role(request, match_id)
    if response:
        return response
    match, officials, role = resolved
    if not role.tracked:
        messages.error(request, "This role cannot be declined online. Please contact the Referees Manager.")
        return redirect('referees:referee_dashboard')

    context = {
        'match': match,
        'officials': officials,
        'role': role.code,
        'role_display': role.label,
        'already_rejected': officials.is_declined(role),
        'match_date': timezone.localdate(match.match_date),
        'today': timezone.localdate(),
    }
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "Please provide a reason for declining this appointment.")
            return render(request, 'referees/decline_appointment.html', context)
        officials.mark_declined(role, reason)
        officials.save(validate=False)
        messages.success(request, f"{role.label} appointment declined. Referees Manager will be notified.")
        return redirect('referees:referee_dashboard')
    return render(request, 'referees/decline_appointment.html', context)


# ------------------------------------------------------------- referees manager
def _days_until(match) -> int:
    return (timezone.localdate(match.match_date) - timezone.localdate()).days


@login_required
@permission_required('referees.appoint_referees', raise_exception=True)
def appoint_match_officials(request, match_id):
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team', 'zone'), id=match_id)
    days_until_match = _days_until(match)
    if days_until_match > APPOINTMENT_WINDOW_DAYS:
        messages.error(
            request,
            f"Cannot appoint officials yet. Match is in {days_until_match} days. "
            f"Officials can only be appointed within {APPOINTMENT_WINDOW_DAYS} days of match.",
        )
        return redirect('matches:match_details', match_id=match.id)

    match_officials = MatchOfficials.objects.filter(match=match).first() or MatchOfficials(match=match)

    if request.method == 'POST':
        form = MatchOfficialsAppointmentForm(request.POST, instance=match_officials)
        if form.is_valid():
            officials = form.save(commit=False)
            officials.status = MatchOfficials.Status.APPOINTED
            officials.appointment_made_by = request.user
            for role in OFFICIAL_ROLES_BY_CODE.values():
                if role.field in form.changed_data:
                    officials.reset_role(role)
            try:
                officials.save()
            except ValidationError as exc:
                for msg in exc.messages:
                    messages.error(request, msg)
            else:
                messages.success(request, f'Match officials appointed for {match}!')
                return redirect('referees:appoint_match_officials', match_id=match.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = MatchOfficialsAppointmentForm(instance=match_officials)

    match_day = timezone.localdate(match.match_date)
    unavailable_ids = set(
        RefereeAvailability.objects.filter(date=match_day, is_available=False).values_list('referee_id', flat=True)
    )
    available_referees = list(Referee.objects.filter(status=Referee.Status.APPROVED, is_active=True))
    for referee in available_referees:
        # NB: historical template semantics — True means "marked unavailable".
        referee.is_available = referee.pk in unavailable_ids

    context = {
        'match': match,
        'form': form,
        'match_officials': match_officials,
        'available_referees': available_referees,
        'days_until_match': days_until_match,
        'can_replace': request.user.has_perm('referees.replace_referee'),
        'OFFICIAL_ROLES': MatchOfficials.Role.choices,
    }
    return render(request, 'referees/appoint_officials.html', context)


@login_required
@permission_required('referees.replace_referee', raise_exception=True)
def replace_referee(request, match_id, role):
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    officials = getattr(match, 'officials', None)
    if officials is None:
        messages.error(request, "No officials appointed for this match.")
        return redirect('matches:match_details', match_id=match.id)

    spec = OFFICIAL_ROLES_BY_CODE.get(role)
    if spec is None:
        messages.error(request, "Invalid role specified.")
        return redirect('referees:appoint_match_officials', match_id=match.id)
    current = getattr(officials, spec.field)

    if request.method == 'POST':
        new_referee = Referee.objects.filter(pk=request.POST.get('new_referee') or None).first()
        if new_referee is None:
            messages.error(request, "Please select a referee.")
            return redirect('referees:replace_referee', match_id=match.id, role=role)
        setattr(officials, spec.field, new_referee)
        officials.reset_role(spec)
        try:
            officials.save()  # full_clean: eligibility, duplicates, availability
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect('referees:replace_referee', match_id=match.id, role=role)
        messages.success(
            request,
            f"{spec.label} replaced successfully! "
            f"Old: {current.full_name if current else 'None'} → New: {new_referee.full_name}",
        )
        return redirect('referees:appoint_match_officials', match_id=match.id)

    available = Referee.objects.filter(status=Referee.Status.APPROVED, is_active=True)
    if current:
        available = available.exclude(pk=current.pk)
    context = {
        'match': match,
        'officials': officials,
        'role': role,
        'role_name': spec.label,
        'current_referee': current,
        'available_referees': available,
        'match_date': timezone.localdate(match.match_date),
    }
    return render(request, 'referees/replace_referee.html', context)


@login_required
@permission_required('referees.appoint_referees', raise_exception=True)
def cancel_appointment(request, match_id):
    """Cancel all officials for a match and notify them."""
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), id=match_id)
    officials = MatchOfficials.objects.filter(match=match).first()
    if officials is None:
        messages.error(request, "No officials appointed for this match.")
        return redirect('matches:match_details', match_id=match.id)

    if request.method == 'POST':
        appointed = [(role.label, referee) for role, referee in officials.appointed()]
        with transaction.atomic():
            officials.delete()
        notified = services.notify_appointment_cancelled(match, appointed)
        logger.info("Appointments for match id=%s cancelled by user id=%s", match.pk, request.user.pk)
        messages.success(
            request,
            f"All appointments for {match} have been cancelled. "
            f"Notifications sent to {notified} of {len(appointed)} official(s).",
        )
        return redirect('dashboard')

    return render(request, 'referees/cancel_appointment_confirm.html', {'match': match, 'officials': officials})


@login_required
@permission_required('referees.appoint_referees', raise_exception=True)
def matches_needing_officials(request):
    now = timezone.now()
    window_end = now + timezone.timedelta(days=APPOINTMENT_WINDOW_DAYS)
    matches = (
        Match.objects.filter(match_date__range=(now, window_end), status='scheduled')
        .select_related('home_team', 'away_team', 'zone', 'officials', *(f'officials__{f}' for f in _REFEREE_RELATED))
        .order_by('round_number', 'match_date')
    )

    needs_officials, appointed_matches, pending_confirmation, confirmed_matches, declined = [], [], [], [], []
    for match in matches:
        officials = getattr(match, 'officials', None)
        if officials is None:
            match.has_declined = False
            needs_officials.append(match)
        elif officials.has_declined:
            match.has_declined = True
            match.declined_roles = officials.declined_roles()
            declined.append(match)
        elif officials.status == MatchOfficials.Status.APPOINTED:
            appointed_matches.append(match)
            pending_confirmation.append(match)
        elif officials.status == MatchOfficials.Status.CONFIRMED:
            appointed_matches.append(match)
            confirmed_matches.append(match)

    t_related = (
        'tournament', 'home_team__team', 'home_team__external_team',
        'away_team__team', 'away_team__external_team',
    )
    context = {
        'needs_officials': needs_officials,
        'appointed_matches': appointed_matches,
        'pending_confirmation': pending_confirmation,
        'confirmed_matches': confirmed_matches,
        'declined_appointments': declined,
        'declined_count': len(declined),
        'today': timezone.localdate(),
        'four_days_later': timezone.localdate(window_end),
        'OFFICIAL_ROLES': MatchOfficials.Role.choices,
        't_needs_officials': TournamentMatch.objects.filter(
            Q(officials__isnull=True) | Q(officials__status='PENDING'),
            status='scheduled', match_date__gte=now,
        ).select_related(*t_related).order_by('match_date'),
        't_appointed': TournamentMatch.objects.filter(
            officials__status__in=['APPOINTED', 'CONFIRMED'], status='scheduled', match_date__gte=now,
        ).select_related('officials', *t_related).order_by('match_date'),
    }
    return render(request, 'referees/matches_needing_officials.html', context)


# ------------------------------------------------------------- JSON for the manager dashboard
def _window_matches():
    today = timezone.localdate()
    return Match.objects.filter(
        match_date__date__range=(today, today + timezone.timedelta(days=APPOINTMENT_WINDOW_DAYS)),
        status='scheduled',
    ).select_related('home_team', 'away_team', 'zone').order_by('match_date')


def _match_json(match) -> dict:
    return {
        'id': match.id,
        'date': timezone.localtime(match.match_date).strftime('%d/%m/%Y'),
        'match_date': timezone.localtime(match.match_date).strftime('%d/%m/%Y'),
        'time': match.kickoff_time or 'TBD',
        'kickoff_time': match.kickoff_time or 'TBD',
        'home_team': match.home_team.team_name,
        'away_team': match.away_team.team_name,
        'venue': match.venue,
        'zone': match.zone.name if match.zone_id else '',
        'round': match.round_number,
        'days_until_match': _days_until(match),
        'days_left': _days_until(match),
    }


@login_required
@permission_required('referees.appoint_referees', raise_exception=True)
@require_GET
def api_urgent_matches(request):
    """Matches inside the appointment window with no officials appointed."""
    matches = _window_matches().filter(officials__isnull=True)[:10]
    return JsonResponse({'matches': [{**_match_json(m), 'status': 'Needs Officials'} for m in matches]})


@login_required
@permission_required('referees.appoint_referees', raise_exception=True)
@require_GET
def api_appointed_matches(request):
    """Matches inside the appointment window that have officials."""
    matches = _window_matches().filter(officials__isnull=False).select_related(
        'officials__main_referee', 'officials__assistant_1', 'officials__assistant_2',
    )[:15]
    data = []
    for match in matches:
        o = match.officials
        data.append({
            **_match_json(match),
            'referee': o.main_referee.full_name if o.main_referee else None,
            'main_referee': o.main_referee.full_name if o.main_referee else None,
            'ar1': o.assistant_1.full_name if o.assistant_1 else None,
            'ar2': o.assistant_2.full_name if o.assistant_2 else None,
            'status': o.status,
            'status_display': 'Confirmed' if o.status == MatchOfficials.Status.CONFIRMED else 'Pending Confirmation',
        })
    return JsonResponse({'matches': data})


@login_required
@permission_required('referees.appoint_referees', raise_exception=True)
@require_GET
def api_available_referees_today(request):
    """Approved, active referees not marked unavailable today."""
    today = timezone.localdate()
    referees = (
        Referee.objects.filter(status=Referee.Status.APPROVED, is_active=True)
        .exclude(availabilities__date=today, availabilities__is_available=False)[:10]
    )
    return JsonResponse({'referees': [
        {
            'id': r.id,
            'name': r.full_name,
            'full_name': r.full_name,
            'initials': f"{r.first_name[:1]}{r.last_name[:1]}",
            'level': r.get_level_display() or 'Not set',
            'grade': r.get_level_display() or '',
            'specialization': r.get_specialization_display() or '',
            'county': r.county or 'Not set',
        }
        for r in referees
    ]})
