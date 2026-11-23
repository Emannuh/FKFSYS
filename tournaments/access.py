"""Role checks and view decorators for the tournaments app.

Built on the shared helpers in ``fkf_league.permissions``. Authenticated
users without the right role get a 403 rather than a login redirect, so a
denial shows up as a denial in logs.
"""
from collections.abc import Callable
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from fkf_league.permissions import is_league_admin, is_referees_manager


def is_tournament_admin(user) -> bool:
    """Superuser, staff or 'League Admin' member."""
    return user.is_authenticated and (user.is_superuser or is_league_admin(user))


def can_appoint_officials(user) -> bool:
    """Tournament admins and the Referees Manager."""
    return is_tournament_admin(user) or (
        user.is_authenticated and is_referees_manager(user)
    )


def role_required(test: Callable[[object], bool]):
    """Require login, then raise 403 unless ``test(user)`` passes."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not test(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


tournament_admin_required = role_required(is_tournament_admin)
officials_manager_required = role_required(can_appoint_officials)
