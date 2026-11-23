"""
fkf_league/context_processors.py

league_settings_context
    Exposes the LeagueSettings singleton as ``{{ league_settings }}``. The lookup is
    lazy (only pages that actually use it pay for the query) and memoised on the
    request, so views and templates share one fetch per request.

site_info_context
    Site-wide constants: ``{{ current_year }}``, ``{{ site_name }}``.
"""
from __future__ import annotations

import logging
from typing import Any

from django.db import DatabaseError
from django.http import HttpRequest
from django.utils import timezone
from django.utils.functional import SimpleLazyObject

logger = logging.getLogger(__name__)

SITE_NAME = 'FKF Meru County League'
_CACHE_ATTR = '_cached_league_settings'


def get_request_league_settings(request: HttpRequest) -> Any:
    """Return LeagueSettings for this request (fetched at most once), or None on DB error."""
    if not hasattr(request, _CACHE_ATTR):
        from teams.models import LeagueSettings  # local import: avoids app-registry import cycles

        try:
            value = LeagueSettings.get_settings()
        except DatabaseError:
            logger.exception('Could not load LeagueSettings')
            value = None
        setattr(request, _CACHE_ATTR, value)
    return getattr(request, _CACHE_ATTR)


def league_settings_context(request: HttpRequest) -> dict[str, Any]:
    return {'league_settings': SimpleLazyObject(lambda: get_request_league_settings(request))}


def site_info_context(request: HttpRequest) -> dict[str, Any]:
    return {
        'current_year': timezone.now().year,
        'site_name': SITE_NAME,
    }
