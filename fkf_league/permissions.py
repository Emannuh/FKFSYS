"""
fkf_league/permissions.py

Single source of truth for role checks. Import these in views (e.g. with
``user_passes_test``) and template tags instead of re-implementing group lookups.

Group membership is fetched once per user object and memoised on it, so calling
several helpers while rendering one request (navigation, role label, view
checks) costs a single query. Like Django's own permission cache, the memo
lives only as long as the user instance (normally one request).
"""
from __future__ import annotations

from typing import Any

# Canonical group names — keep in sync with the Group rows in the database.
GROUP_LEAGUE_ADMIN = 'League Admin'
GROUP_LEAGUE_MANAGER = 'League Manager'
GROUP_REFEREES_MANAGER = 'Referees Manager'
GROUP_TEAM_MANAGERS = 'Team Managers'
GROUP_REFEREE = 'Referee'

_CACHE_ATTR = '_fkf_group_names'


def user_group_names(user: Any) -> frozenset[str]:
    """Return the names of the user's groups (memoised on the user instance)."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return frozenset()
    cached = getattr(user, _CACHE_ATTR, None)
    if cached is None:
        cached = frozenset(user.groups.values_list('name', flat=True))
        setattr(user, _CACHE_ATTR, cached)
    return cached


def _in_any_group(user: Any, *names: str) -> bool:
    return not user_group_names(user).isdisjoint(names)


def _is_staff(user: Any) -> bool:
    return bool(getattr(user, 'is_staff', False))


def is_super_admin(user: Any) -> bool:
    """Superuser only — user management and full system access."""
    return bool(getattr(user, 'is_superuser', False))


def is_league_admin(user: Any) -> bool:
    """Superuser, staff or 'League Admin' group member."""
    return bool(getattr(user, "is_superuser", False)) or _is_staff(user) or _in_any_group(user, GROUP_LEAGUE_ADMIN)


def is_league_admin_or_manager(user: Any) -> bool:
    """Staff, 'League Admin' or 'League Manager' group member."""
    return _is_staff(user) or _in_any_group(user, GROUP_LEAGUE_ADMIN, GROUP_LEAGUE_MANAGER)


def is_team_manager(user: Any) -> bool:
    """'Team Managers' group member."""
    return _in_any_group(user, GROUP_TEAM_MANAGERS)


def is_referee(user: Any) -> bool:
    """'Referee' group member."""
    return _in_any_group(user, GROUP_REFEREE)


def is_referees_manager(user: Any) -> bool:
    """Staff or 'Referees Manager' group member."""
    return _is_staff(user) or _in_any_group(user, GROUP_REFEREES_MANAGER)


def is_any_admin(user: Any) -> bool:
    """Any admin-level access: staff or any of the admin groups."""
    return _is_staff(user) or _in_any_group(
        user, GROUP_LEAGUE_ADMIN, GROUP_LEAGUE_MANAGER, GROUP_REFEREES_MANAGER,
    )


def role_label(user: Any) -> str:
    """Human-readable role for display (sidebar, user lists)."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return 'Guest'
    if is_super_admin(user):
        return 'Super Admin'
    if _is_staff(user):
        return 'League Admin'
    groups = sorted(user_group_names(user))
    return groups[0] if groups else 'Member'
