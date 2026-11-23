"""Request-level audit logging (registered in settings.MIDDLEWARE).

Records one ``ActivityLog`` row for every state-changing request made by an
authenticated user, unless the view already wrote an explicit entry via
``log_activity(..., request=request)``. Login/logout are recorded by the auth
signal handlers in ``admin_dashboard.signals`` instead.

Only metadata is stored — URL name, path, method, status, URL kwargs and the
*names* of submitted form fields. Submitted values are never stored.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.shortcuts import resolve_url

from .activity_logger import REQUEST_LOGGED_ATTR, Action, log_activity

logger = logging.getLogger('admin_dashboard.audit')

STATE_CHANGING_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})
AUTH_URL_NAMES = frozenset({'login', 'logout'})
IGNORED_FIELDS = frozenset({'csrfmiddlewaretoken'})


def classify(path: str) -> str:
    """Map a request path to an audit action."""
    p = path.lower()
    if 'generate-fixtures' in p or 'generate_fixtures' in p:
        return Action.FIXTURE_REGENERATE if 'regenerate' in p else Action.FIXTURE_GENERATE
    if 'reschedule' in p:
        return Action.MATCH_RESCHEDULE
    if 'transfer' in p:
        return Action.PLAYER_TRANSFER
    if 'squad' in p:
        if 'approve' in p:
            return Action.SQUAD_APPROVE
        if 'reject' in p:
            return Action.SQUAD_REJECT
        return Action.MATCHDAY_SQUAD_SUBMIT
    if p.startswith('/payments/'):
        return Action.PAYMENT_ACTION
    if p.startswith('/referees/'):
        return Action.REFEREE_REGISTER if 'register' in p else Action.REFEREE_ACTION
    if p.startswith('/teams/'):
        if 'player' in p:
            if 'add' in p or 'register' in p:
                return Action.PLAYER_CREATE
            if 'delete' in p:
                return Action.PLAYER_DELETE
            return Action.PLAYER_UPDATE
        if 'register' in p:
            return Action.TEAM_CREATE
        if 'delete' in p:
            return Action.TEAM_DELETE
        return Action.TEAM_UPDATE
    if p.startswith('/matches/'):
        if 'create' in p:
            return Action.MATCH_CREATE
        if 'delete' in p:
            return Action.MATCH_DELETE
        return Action.MATCH_UPDATE
    if p.startswith(('/admin-dashboard/', '/admin/')):
        return Action.ADMIN_ACTION
    return Action.OTHER


def _is_login_redirect(response) -> bool:
    if response.status_code not in (301, 302, 303, 307, 308):
        return False
    location = response.get('Location', '')
    login_urls = (str(resolve_url(settings.LOGIN_URL)), '/admin/login/')
    return location.startswith(login_urls)


class ActivityLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._record(request, response)
        except Exception:  # never let auditing break a request
            logger.exception("Activity logging middleware failed")
        return response

    def _record(self, request, response) -> None:
        if request.method not in STATE_CHANGING_METHODS:
            return
        if getattr(request, REQUEST_LOGGED_ATTR, False):
            return
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return

        match = getattr(request, 'resolver_match', None)
        url_name = match.view_name if match else ''
        if match and match.url_name in AUTH_URL_NAMES:
            return

        status = response.status_code
        if status == 403 or _is_login_redirect(response):
            action = Action.ACCESS_DENIED
        elif 200 <= status < 400:
            action = classify(request.path)
        else:
            return

        verb = 'was denied' if action == Action.ACCESS_DENIED else 'performed'
        log_activity(
            user=user,
            action=action,
            description=f"{user.get_username()} {verb} {request.method} {url_name or request.path}",
            request=request,
            extra_data={
                'path': request.path[:300],
                'url_name': url_name,
                'method': request.method,
                'status': status,
                'url_kwargs': {k: str(v) for k, v in (match.kwargs.items() if match else [])},
                'fields': sorted(k for k in request.POST.keys() if k not in IGNORED_FIELDS)[:50],
            },
        )
