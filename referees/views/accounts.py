"""Referee registration, profile, availability and referee administration."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from matches.models import Match

from ..forms import RefereeProfileUpdateForm, RefereeRegistrationForm
from ..models import MatchReport, Referee, RefereeAvailability
from .. import services
from ._common import current_referee, manager_required


def _status_counts() -> dict:
    counts = Referee.objects.aggregate(
        total_count=Count('pk'),
        approved_count=Count('pk', filter=Q(status=Referee.Status.APPROVED)),
        pending_count=Count('pk', filter=Q(status=Referee.Status.PENDING)),
        rejected_count=Count('pk', filter=Q(status=Referee.Status.REJECTED)),
        suspended_count=Count('pk', filter=Q(status=Referee.Status.SUSPENDED)),
    )
    return counts


# ------------------------------------------------------------- public
def referee_registration(request):
    """Public registration: creates a pending Referee (no user account yet)."""
    if request.method == 'POST':
        form = RefereeRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            referee = form.save(commit=False)
            referee.status = Referee.Status.PENDING
            referee.is_active = False
            referee.save()
            messages.success(
                request,
                f"Registration successful. Thank you, {referee.full_name}! Your application is "
                "pending approval; once approved you will receive an email with your login ID "
                "and a link to set your password.",
            )
            return redirect('referees:login_instructions')
    else:
        form = RefereeRegistrationForm()
    return render(request, 'referees/register.html', {'form': form})


def login_instructions(request):
    context = {}
    referee = current_referee(request.user)
    if referee:
        context.update(referee=referee, status=referee.status)
    return render(request, 'referees/login_instructions.html', context)


# ------------------------------------------------------------- referee self-service
@login_required
def referee_profile(request):
    referee = current_referee(request.user)
    if referee is None:
        messages.error(request, "You don't have a referee profile.")
        return redirect('referees:referee_registration')

    if request.method == 'POST':
        form = RefereeProfileUpdateForm(request.POST, request.FILES, instance=referee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('referees:referee_profile')
    else:
        form = RefereeProfileUpdateForm(instance=referee)
    return render(request, 'referees/profile.html', {'referee': referee, 'form': form})


@login_required
def referee_availability(request):
    referee = current_referee(request.user)
    if referee is None:
        messages.error(request, 'You are not registered as a referee.')
        return redirect('referees:referee_registration')
    if not referee.can_be_appointed():
        messages.warning(request, 'You cannot set availability until approved.')
        return redirect('frontend:home')

    today = timezone.localdate()
    if request.method == 'POST':
        is_available = request.POST.get('is_available') == 'true'
        reason = request.POST.get('reason', '').strip()
        try:
            day = date.fromisoformat(request.POST.get('date', ''))
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return redirect('referees:referee_availability')
        if day < today:
            messages.error(request, 'You cannot set availability for a past date.')
            return redirect('referees:referee_availability')
        RefereeAvailability.objects.update_or_create(
            referee=referee, date=day,
            defaults={'is_available': is_available, 'reason': '' if is_available else reason},
        )
        status = "Available" if is_available else "Unavailable"
        messages.success(request, f'Availability set to {status} for {day}.')
        return redirect('referees:referee_availability')

    context = {
        'referee': referee,
        'availabilities': RefereeAvailability.objects.filter(referee=referee, date__gte=today).order_by('date'),
        'today': today,
        'next_30_days': [today + timezone.timedelta(days=i) for i in range(30)],
    }
    return render(request, 'referees/availability.html', context)


# ------------------------------------------------------------- referee administration
@manager_required
def admin_referee_dashboard(request):
    now = timezone.now()
    report_counts = MatchReport.objects.aggregate(
        pending_report_count=Count('pk', filter=Q(status=MatchReport.Status.SUBMITTED)),
        approved_reports_count=Count('pk', filter=Q(status=MatchReport.Status.APPROVED)),
    )
    context = {
        **_status_counts(),
        **report_counts,
        'pending_referees': Referee.objects.filter(status=Referee.Status.PENDING).order_by('-date_joined')[:10],
        'recent_reports': MatchReport.objects.select_related('match__home_team', 'match__away_team', 'referee')
                                             .order_by('-created_at')[:10],
        'pending_report_list': MatchReport.objects.filter(status=MatchReport.Status.SUBMITTED)
                                                  .select_related('match__home_team', 'match__away_team', 'referee')
                                                  .order_by('-submitted_at')[:5],
        'matches_needing_officials': Match.objects.filter(
            match_date__gte=now, match_date__lte=now + timezone.timedelta(days=4),
        ).filter(Q(officials__isnull=True) | Q(officials__status='PENDING')).count(),
    }
    return render(request, 'referees/admin_dashboard.html', context)


@manager_required
def pending_referees(request):
    counts = _status_counts()
    context = {
        'pending_referees': Referee.objects.filter(status=Referee.Status.PENDING).order_by('-date_joined'),
        'approved_count': counts['approved_count'],
        'rejected_count': counts['rejected_count'],
    }
    return render(request, 'referees/admin/pending_referees.html', context)


@manager_required
def all_referees(request):
    referees = Referee.objects.all()
    if status := request.GET.get('status'):
        referees = referees.filter(status=status)
    active = request.GET.get('active')
    if active == 'active':
        referees = referees.filter(is_active=True)
    elif active == 'inactive':
        referees = referees.filter(is_active=False)
    if level := request.GET.get('level'):
        referees = referees.filter(level=level)
    if specialization := request.GET.get('specialization'):
        referees = referees.filter(specialization=specialization)
    if county := request.GET.get('county', '').strip():
        referees = referees.filter(county__icontains=county)

    context = {
        'referees': referees.order_by('-date_joined'),
        'level_choices': Referee.Level.choices,
        'status_choices': Referee.Status.choices,
        **_status_counts(),
    }
    return render(request, 'referees/admin/all_referees.html', context)


@manager_required
def approve_referee(request, referee_id):
    referee = get_object_or_404(Referee, id=referee_id)
    if request.method == 'POST':
        group_found, email_sent = services.approve_referee(referee, request.user, request)
        messages.success(
            request,
            f"Referee {referee.full_name} has been approved. Login ID: {referee.unique_id}.",
        )
        if email_sent:
            messages.info(request, f"A set-password link has been emailed to {referee.email}.")
        else:
            messages.warning(
                request,
                "The set-password email could not be sent. Ask the referee to use "
                "'Forgot password' on the login page with their registered email.",
            )
        if not group_found:
            messages.warning(request, "Referee group not found. Please create it in Django Admin.")
        return redirect('referees:pending_referees')
    return render(request, 'referees/admin/approve_referee.html', {'referee': referee})


@manager_required
def reject_referee(request, referee_id):
    referee = get_object_or_404(Referee, id=referee_id)
    if request.method == 'POST':
        referee.reject(request.POST.get('rejection_reason', '').strip())
        messages.success(request, f'Referee {referee.full_name} has been rejected.')
        return redirect('referees:pending_referees')
    return render(request, 'referees/admin/reject_referee.html', {'referee': referee})


@manager_required
@require_POST
def suspend_referee(request, referee_id):
    referee = get_object_or_404(Referee, id=referee_id)
    reason = request.POST.get('suspension_reason', '').strip()
    if not reason:
        messages.error(request, 'Please give a reason for the suspension.')
    elif referee.status != Referee.Status.APPROVED:
        messages.error(request, 'Only approved referees can be suspended.')
    else:
        referee.suspend(reason)
        messages.success(request, f'Referee {referee.full_name} has been suspended.')
    return redirect('referees:all_referees')


@manager_required
@require_POST
def reactivate_referee(request, referee_id):
    referee = get_object_or_404(Referee, id=referee_id)
    if referee.status not in (Referee.Status.SUSPENDED, Referee.Status.APPROVED):
        messages.error(request, 'Only suspended referees can be reactivated.')
    else:
        referee.reactivate()
        messages.success(request, f'Referee {referee.full_name} has been reactivated.')
    return redirect('referees:all_referees')
