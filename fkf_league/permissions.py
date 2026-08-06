"""
fkf_league/permissions.py

Single source of truth for all permission-check functions.
Import these in views instead of redefining them locally.
"""


def is_super_admin(user):
    """Superuser only — for user management and full system access."""
    return user.is_superuser


def is_league_admin(user):
    """Staff OR 'League Admin' group member."""
    return user.is_staff or user.groups.filter(name='League Admin').exists()


def is_league_admin_or_manager(user):
    """Staff, 'League Admin' or 'League Manager' group."""
    return user.is_staff or user.groups.filter(
        name__in=['League Admin', 'League Manager']
    ).exists()


def is_team_manager(user):
    """'Team Managers' group member."""
    return user.groups.filter(name='Team Managers').exists()


def is_referee(user):
    """'Referee' group member."""
    return user.groups.filter(name='Referee').exists()


def is_referees_manager(user):
    """'Referees Manager' group member OR staff."""
    return user.is_staff or user.groups.filter(name='Referees Manager').exists()


def is_any_admin(user):
    """Any admin-level access (staff or any admin group)."""
    return user.is_staff or user.groups.filter(
        name__in=['League Admin', 'League Manager', 'Referees Manager']
    ).exists()
