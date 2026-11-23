"""Shared helpers for the referees views."""
from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from fkf_league.permissions import is_league_admin, is_referees_manager

from ..models import Referee


def role_required(test):
    """login_required + 403 (not a login redirect) for authenticated users failing ``test``."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not test(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


manager_required = role_required(is_referees_manager)
league_admin_required = role_required(is_league_admin)


def current_referee(user) -> Referee | None:
    """The Referee profile linked to ``user``, or None."""
    if not user.is_authenticated:
        return None
    return Referee.objects.filter(user=user).first()
