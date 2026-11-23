"""Shared access-control decorators for admin_dashboard views."""
from __future__ import annotations

from functools import wraps
from typing import Callable

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from fkf_league.permissions import is_league_admin, is_super_admin


def role_required(test: Callable) -> Callable:
    """Anonymous → login redirect; authenticated but failing ``test`` → 403."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not test(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _is_staff(user) -> bool:
    return user.is_active and user.is_staff


league_admin_required = role_required(is_league_admin)
superuser_required = role_required(is_super_admin)
staff_required = role_required(_is_staff)
