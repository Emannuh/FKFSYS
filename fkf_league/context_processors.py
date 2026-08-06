"""
fkf_league/context_processors.py

Global template context processors.

league_settings_context:
    Makes LeagueSettings available in every template as {{ league_settings }}
    without each view needing to call LeagueSettings.get_settings().

    This replaces the repeated pattern across views:
        settings = LeagueSettings.get_settings()
        context = { ..., 'league_settings': settings, ... }

site_info_context:
    Makes basic site metadata available everywhere (current year, site name).
"""
from django.utils import timezone


def league_settings_context(request):
    """
    Inject the singleton LeagueSettings into every template context.
    Uses a per-request cache on the request object to avoid multiple DB hits
    within the same request cycle.
    """
    if not hasattr(request, '_cached_league_settings'):
        try:
            from teams.models import LeagueSettings
            request._cached_league_settings = LeagueSettings.get_settings()
        except Exception:
            request._cached_league_settings = None
    return {'league_settings': request._cached_league_settings}


def site_info_context(request):
    """Inject site-wide constants available in all templates."""
    return {
        'current_year': timezone.now().year,
        'site_name':    'FKF Meru County League',
    }
