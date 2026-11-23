"""Keep referees whose application is not approved out of the referee-only pages."""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from .models import Referee

# Referee self-service pages that require an approved profile.
GUARDED_URL_NAMES = frozenset({
    'referees:referee_dashboard',
    'referees:referee_profile',
    'referees:referee_availability',
    'referees:view_report',
    'referees:submit_match_report',
    'referees:submit_comprehensive_report',
    'referees:confirm_appointment',
    'referees:decline_appointment',
    'referees:submit_prematch_form',
})


class RefereeApprovalCheck:
    """
    Redirect logged-in referees whose status is pending/rejected/suspended to the
    login-instructions page when they open a referee self-service page.
    Staff and users without a referee profile are never affected.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self._check(request)
        return response or self.get_response(request)

    def _check(self, request):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated or user.is_staff:
            return None
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return None
        if match.view_name not in GUARDED_URL_NAMES:
            return None

        referee = Referee.objects.filter(user=user).only('status', 'rejection_reason').first()
        if referee is None or referee.status == Referee.Status.APPROVED:
            return None

        if referee.status == Referee.Status.PENDING:
            messages.info(request, 'Your account is pending approval. You will be notified once approved.')
        elif referee.status == Referee.Status.REJECTED:
            messages.error(
                request,
                f'Your application has been rejected. Reason: {referee.rejection_reason or "No reason provided"}',
            )
        else:
            messages.error(request, 'Your referee account is suspended. Please contact the Referees Manager.')
        return redirect('referees:login_instructions')
