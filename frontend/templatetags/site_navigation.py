"""
frontend/templatetags/site_navigation.py

Role-aware navigation data for the layouts. Tags return plain lists/dicts; the
markup lives in templates (base.html, base_dashboard.html, partials/).

    {% load site_navigation %}
    {% site_top_nav as items %}      public top navigation
    {% admin_dropdown as sections %} staff "Admin" menu (public layout)
    {% footer_sections as sections %}
    {% social_links as links %}
    {% dashboard_nav as sections %}  dashboard sidebar

Item dicts: ``title``, ``icon``, ``url`` (resolved), ``is_active``, optional ``danger``.
Items whose URL name no longer resolves are dropped rather than rendered as dead links.
"""
from __future__ import annotations

from typing import Any

from django import template
from django.urls import NoReverseMatch, reverse

from fkf_league.permissions import is_referee, is_team_manager

register = template.Library()

NavItem = dict[str, Any]
NavSection = dict[str, Any]


def _resolve(items: list[NavItem], path: str = '') -> list[NavItem]:
    """Resolve ``url_name`` → ``url``, mark the active item, drop unresolvable items."""
    resolved = []
    for item in items:
        item = dict(item)
        url_name = item.pop('url_name', None)
        if url_name:
            try:
                item['url'] = reverse(url_name)
            except NoReverseMatch:
                continue
        url = item.get('url', '')
        item['is_active'] = bool(path and url) and (
            path == url or (url != '/' and path.startswith(url))
        )
        resolved.append(item)
    return resolved


def _resolve_sections(sections: list[NavSection], path: str = '') -> list[NavSection]:
    out = []
    for section in sections:
        items = _resolve(section['items'], path)
        if items:
            out.append({**section, 'items': items})
    return out


def _user_and_path(context: template.Context) -> tuple[Any, str]:
    request = context.get('request')
    user = context.get('user') or getattr(request, 'user', None)
    return user, getattr(request, 'path', '') if request else ''


# ── Public layout ─────────────────────────────────────────────────────────

_PUBLIC_NAV: list[NavItem] = [
    {'title': 'Fixtures', 'icon': 'fas fa-calendar', 'url_name': 'matches:fixtures'},
    {'title': 'Tables', 'icon': 'fas fa-table', 'url_name': 'matches:league_tables'},
    {'title': 'Teams', 'icon': 'fas fa-users', 'url_name': 'teams:all_teams'},
    {'title': 'Tournaments', 'icon': 'fas fa-trophy', 'url_name': 'tournaments:tournament_list'},
    {'title': 'Rules', 'icon': 'fas fa-book', 'url_name': 'frontend:rules'},
]

_ADMIN_SECTIONS: list[NavSection] = [
    {'title': 'Dashboards', 'icon': 'fas fa-tachometer-alt', 'items': [
        {'title': 'Dashboard', 'icon': 'fas fa-chart-line', 'url_name': 'dashboard'},
        {'title': 'Referees Manager', 'icon': 'fas fa-clipboard-list', 'url_name': 'referees:referee_dashboard'},
    ]},
    {'title': 'League Management', 'icon': 'fas fa-trophy', 'items': [
        {'title': 'League Admin', 'icon': 'fas fa-cogs', 'url_name': 'teams:dashboard'},
        {'title': 'Approve Teams', 'icon': 'fas fa-user-check', 'url_name': 'admin_dashboard:approve_registrations'},
        {'title': 'Assign Zones', 'icon': 'fas fa-map-marker-alt', 'url_name': 'admin_dashboard:assign_zones'},
        {'title': 'Manage Transfers', 'icon': 'fas fa-exchange-alt', 'url_name': 'admin_dashboard:manage_transfers'},
        {'title': 'Manage Players', 'icon': 'fas fa-users', 'url_name': 'teams:admin_manage_players'},
        {'title': 'Team Officials', 'icon': 'fas fa-id-card', 'url_name': 'teams:admin_manage_officials'},
    ]},
    {'title': 'Tournament Management', 'icon': 'fas fa-trophy', 'items': [
        {'title': 'Tournament Dashboard', 'icon': 'fas fa-trophy', 'url_name': 'tournaments:admin_dashboard'},
        {'title': 'Create Tournament', 'icon': 'fas fa-plus-circle', 'url_name': 'tournaments:create_tournament'},
    ]},
    {'title': 'Match Management', 'icon': 'fas fa-futbol', 'items': [
        {'title': 'Generate Fixtures', 'icon': 'fas fa-random', 'url_name': 'admin_dashboard:generate_fixtures_admin'},
        {'title': 'Reschedule Fixtures', 'icon': 'fas fa-calendar-alt', 'url_name': 'admin_dashboard:reschedule_fixtures_admin'},
        {'title': 'Manage Matches', 'icon': 'fas fa-edit', 'url_name': 'matches:manage_matches'},
        {'title': 'Appoint Officials', 'icon': 'fas fa-user-tie', 'url_name': 'referees:matches_needing_officials'},
    ]},
    {'title': 'Referee Management', 'icon': 'fas fa-flag', 'items': [
        {'title': 'Pending Referees', 'icon': 'fas fa-user-clock', 'url_name': 'referees:pending_referees'},
        {'title': 'All Referees', 'icon': 'fas fa-list', 'url_name': 'referees:all_referees'},
        {'title': 'Pre-Match Forms Admin', 'icon': 'fas fa-file-signature', 'url_name': 'referees:pending_prematch_forms_admin'},
        {'title': 'Pre-Match Forms Manager', 'icon': 'fas fa-file-alt', 'url_name': 'referees:pending_prematch_forms_manager'},
    ]},
    {'title': 'Discipline & Reports', 'icon': 'fas fa-gavel', 'items': [
        {'title': 'Manage Suspensions', 'icon': 'fas fa-ban', 'url_name': 'admin_dashboard:view_suspensions'},
        {'title': 'Approve Match Reports', 'icon': 'fas fa-clipboard-check', 'url_name': 'referees:pending_reports'},
        {'title': 'Statistics Dashboard', 'icon': 'fas fa-chart-bar', 'url_name': 'admin_dashboard:statistics_dashboard'},
    ]},
]

_SUPERUSER_ADMIN_SECTION: NavSection = {'title': 'System Admin', 'icon': 'fas fa-server', 'items': [
    {'title': 'Django Admin Panel', 'icon': 'fas fa-tools', 'url_name': 'admin:index'},
]}

_FOOTER_SECTIONS: list[NavSection] = [
    {'title': 'League', 'items': [
        {'title': 'Fixtures', 'url_name': 'matches:fixtures'},
        {'title': 'Tables', 'url_name': 'matches:league_tables'},
        {'title': 'Top Scorers', 'url_name': 'matches:top_scorers'},
        {'title': 'Teams', 'url_name': 'teams:all_teams'},
        {'title': 'Tournaments', 'url_name': 'tournaments:tournament_list'},
    ]},
    {'title': 'Get involved', 'items': [
        {'title': 'Register Team', 'url_name': 'teams:team_registration'},
        {'title': 'Become a Referee', 'url_name': 'referees:referee_registration'},
        {'title': 'League Rules', 'url_name': 'frontend:rules'},
        {'title': 'About Us', 'url_name': 'frontend:about'},
        {'title': 'Contact', 'url_name': 'frontend:contact'},
    ]},
]

# Placeholder URLs until the league publishes official accounts; templates hide '#' links.
_SOCIAL_LINKS: list[NavItem] = [
    {'title': 'Facebook', 'icon': 'fab fa-facebook', 'url': '#'},
    {'title': 'X (Twitter)', 'icon': 'fab fa-twitter', 'url': '#'},
    {'title': 'Instagram', 'icon': 'fab fa-instagram', 'url': '#'},
    {'title': 'YouTube', 'icon': 'fab fa-youtube', 'url': '#'},
]


@register.simple_tag(takes_context=True)
def site_top_nav(context: template.Context) -> list[NavItem]:
    """Public top navigation (login/dashboard buttons are rendered by the layout)."""
    _user, path = _user_and_path(context)
    return _resolve(_PUBLIC_NAV, path)


@register.simple_tag(takes_context=True)
def admin_dropdown(context: template.Context) -> list[NavSection]:
    """Staff-only admin menu sections for the public layout."""
    user, _path = _user_and_path(context)
    if not user or not getattr(user, 'is_staff', False):
        return []
    sections = list(_ADMIN_SECTIONS)
    if user.is_superuser:
        sections.append(_SUPERUSER_ADMIN_SECTION)
    return _resolve_sections(sections)


@register.simple_tag
def footer_sections() -> list[NavSection]:
    return _resolve_sections(_FOOTER_SECTIONS)


@register.simple_tag
def social_links() -> list[NavItem]:
    return [dict(link) for link in _SOCIAL_LINKS]


# ── Dashboard layout ──────────────────────────────────────────────────────

_DASH_MAIN: NavSection = {'title': 'Main', 'items': [
    {'title': 'Dashboard', 'icon': 'fas fa-tachometer-alt', 'url_name': 'dashboard'},
]}

_DASH_STAFF: list[NavSection] = [
    {'title': 'League', 'items': [
        {'title': 'Teams', 'icon': 'fas fa-users', 'url_name': 'teams:dashboard'},
        {'title': 'Players', 'icon': 'fas fa-user-friends', 'url_name': 'teams:admin_manage_players'},
        {'title': 'Team Officials', 'icon': 'fas fa-user-tie', 'url_name': 'teams:admin_manage_officials'},
        {'title': 'Transfers', 'icon': 'fas fa-exchange-alt', 'url_name': 'admin_dashboard:manage_transfers'},
        {'title': 'Approve Teams', 'icon': 'fas fa-user-check', 'url_name': 'admin_dashboard:approve_registrations'},
    ]},
    {'title': 'Matches', 'items': [
        {'title': 'Manage Matches', 'icon': 'fas fa-futbol', 'url_name': 'matches:manage_matches'},
        {'title': 'Generate Fixtures', 'icon': 'fas fa-calendar-plus', 'url_name': 'admin_dashboard:generate_fixtures_admin'},
        {'title': 'Reschedule', 'icon': 'fas fa-calendar-alt', 'url_name': 'admin_dashboard:reschedule_fixtures_admin'},
        {'title': 'Appoint Officials', 'icon': 'fas fa-user-check', 'url_name': 'referees:matches_needing_officials'},
    ]},
    {'title': 'Referees', 'items': [
        {'title': 'Referee Dashboard', 'icon': 'fas fa-flag', 'url_name': 'referees:referee_dashboard'},
        {'title': 'All Referees', 'icon': 'fas fa-list-ul', 'url_name': 'referees:all_referees'},
        {'title': 'Pending Approvals', 'icon': 'fas fa-user-clock', 'url_name': 'referees:pending_referees'},
        {'title': 'Pre-Match Forms', 'icon': 'fas fa-file-signature', 'url_name': 'referees:pending_prematch_forms_admin'},
    ]},
    {'title': 'Reports', 'items': [
        {'title': 'Statistics', 'icon': 'fas fa-chart-bar', 'url_name': 'admin_dashboard:statistics_dashboard'},
        {'title': 'Match Reports', 'icon': 'fas fa-file-alt', 'url_name': 'admin_dashboard:approve_reports'},
        {'title': 'Suspensions', 'icon': 'fas fa-ban', 'url_name': 'admin_dashboard:view_suspensions'},
        {'title': 'Activity Log', 'icon': 'fas fa-history', 'url_name': 'admin_dashboard:activity_logs'},
    ]},
    {'title': 'Tournaments', 'items': [
        {'title': 'Tournaments', 'icon': 'fas fa-trophy', 'url_name': 'tournaments:admin_dashboard'},
        {'title': 'Create Tournament', 'icon': 'fas fa-plus-circle', 'url_name': 'tournaments:create_tournament'},
    ]},
]

_DASH_SUPERUSER: NavSection = {'title': 'System', 'items': [
    {'title': 'User Management', 'icon': 'fas fa-users-cog', 'url_name': 'admin_dashboard:manage_league_admins'},
    {'title': 'Styleguide', 'icon': 'fas fa-palette', 'url_name': 'frontend:styleguide'},
    {'title': 'Django Admin', 'icon': 'fas fa-tools', 'url_name': 'admin:index'},
]}

_DASH_TEAM_MANAGER: NavSection = {'title': 'My Team', 'items': [
    {'title': 'Team Overview', 'icon': 'fas fa-shield-alt', 'url_name': 'dashboard'},
    {'title': 'Add Players', 'icon': 'fas fa-user-plus', 'url_name': 'teams:add_players_approved'},
    {'title': 'Officials', 'icon': 'fas fa-user-tie', 'url_name': 'teams:team_officials'},
    {'title': 'Kit Colors', 'icon': 'fas fa-tshirt', 'url_name': 'teams:select_kit_colors'},
    {'title': 'Transfer Search', 'icon': 'fas fa-exchange-alt', 'url_name': 'teams:search_players'},
    {'title': 'My Transfers', 'icon': 'fas fa-paper-plane', 'url_name': 'teams:my_transfer_requests'},
]}

_DASH_REFEREE: NavSection = {'title': 'Officiating', 'items': [
    {'title': 'My Dashboard', 'icon': 'fas fa-flag', 'url_name': 'dashboard'},
    {'title': 'Availability', 'icon': 'fas fa-calendar-check', 'url_name': 'referees:referee_availability'},
    {'title': 'My Profile', 'icon': 'fas fa-id-card', 'url_name': 'referees:referee_profile'},
]}

_DASH_PUBLIC: NavSection = {'title': 'Public', 'items': [
    {'title': 'League Tables', 'icon': 'fas fa-table', 'url_name': 'matches:league_tables'},
    {'title': 'Fixtures', 'icon': 'fas fa-calendar', 'url_name': 'matches:fixtures'},
    {'title': 'All Tournaments', 'icon': 'fas fa-globe', 'url_name': 'tournaments:tournament_list'},
]}


@register.simple_tag(takes_context=True)
def dashboard_nav(context: template.Context) -> list[NavSection]:
    """Sidebar sections for the dashboard layout, filtered by role."""
    user, path = _user_and_path(context)
    sections = [_DASH_MAIN]
    if user and getattr(user, 'is_staff', False):
        sections += _DASH_STAFF
        if user.is_superuser:
            sections.append(_DASH_SUPERUSER)
    if is_team_manager(user):
        sections.append(_DASH_TEAM_MANAGER)
    if is_referee(user):
        sections.append(_DASH_REFEREE)
    sections.append(_DASH_PUBLIC)
    return _resolve_sections(sections, path)
