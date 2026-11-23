"""
teams/access.py

Object-level authorisation helpers for the teams app.

Role checks come from ``fkf_league.permissions``; this module answers the
narrower question "may *this* user act on *this* team?".
"""
from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from fkf_league.permissions import is_any_admin, is_league_admin_or_manager

from .models import Team


def get_managed_team(user, *, approved_only: bool = True) -> Team | None:
    """Return the team managed by ``user`` (approved only by default)."""
    if not user.is_authenticated:
        return None
    qs = Team.objects.filter(manager=user)
    if approved_only:
        qs = qs.filter(status=Team.Status.APPROVED)
    return qs.select_related('zone').first()


def can_view_team(user, team: Team) -> bool:
    """Admins (incl. Referees Manager) may view any team; a manager only their own."""
    if not user.is_authenticated:
        return False
    return is_any_admin(user) or team.manager_id == user.pk


def can_manage_team(user, team: Team) -> bool:
    """League admins/managers may edit any team; a manager only their own."""
    if not user.is_authenticated:
        return False
    return is_league_admin_or_manager(user) or team.manager_id == user.pk


def ensure_can_view_team(user, team: Team) -> None:
    if not can_view_team(user, team):
        raise PermissionDenied


def ensure_can_manage_team(user, team: Team) -> None:
    if not can_manage_team(user, team):
        raise PermissionDenied


def league_staff_required(view_func):
    """Login + staff / League Admin / League Manager, else 403."""
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_league_admin_or_manager(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped


def any_admin_required(view_func):
    """Login + any admin role (staff, League Admin/Manager, Referees Manager), else 403."""
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_any_admin(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped
