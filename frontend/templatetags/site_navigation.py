from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()


def _user_in_group(user, group_name):
    try:
        return user.groups.filter(name=group_name).exists()
    except Exception:
        return False


def _reverse_url(name):
    try:
        return reverse(name)
    except (NoReverseMatch, TypeError):
        return ''


def _normalize_items(items, path=''):
    for item in items:
        if item.get('url_name'):
            item['url'] = _reverse_url(item['url_name'])
        if item.get('url') and path:
            item['is_active'] = path == item['url'] or path.startswith(item['url'])
        else:
            item['is_active'] = False
    return items


def _build_site_nav(user):
    items = [
        {'title': 'Home', 'icon': 'fas fa-home', 'url_name': 'frontend:home'},
        {'title': 'Register Team', 'icon': 'fas fa-user-plus', 'url_name': 'teams:team_registration'},
        {'title': 'Teams', 'icon': 'fas fa-users', 'url_name': 'teams:all_teams'},
        {'title': 'League Tables', 'icon': 'fas fa-table', 'url_name': 'matches:league_tables'},
        {'title': 'Fixtures', 'icon': 'fas fa-calendar', 'url_name': 'matches:fixtures'},
        {'title': 'Tournaments', 'icon': 'fas fa-globe', 'url_name': 'tournaments:tournament_list'},
    ]

    if not user or not user.is_authenticated:
        items.append({'title': 'Login', 'icon': 'fas fa-sign-in-alt', 'url_name': 'login'})

    return items


def _build_admin_dropdown(user):
    if not user or not user.is_staff:
        return []

    sections = []
    sections.append({
        'title': 'Dashboards',
        'icon': 'fas fa-tachometer-alt',
        'items': [
            {'title': 'Dashboard', 'icon': 'fas fa-chart-line', 'url_name': 'dashboard'},
            {'title': 'Referees Manager', 'icon': 'fas fa-clipboard-list', 'url_name': 'referees:referee_dashboard'},
        ]
    })
    sections.append({
        'title': 'League Management',
        'icon': 'fas fa-trophy',
        'items': [
            {'title': 'League Admin', 'icon': 'fas fa-cogs', 'url_name': 'teams:dashboard'},
            {'title': 'Approve Teams', 'icon': 'fas fa-user-check', 'url_name': 'admin_dashboard:approve_registrations'},
            {'title': 'Assign Zones', 'icon': 'fas fa-map-marker-alt', 'url_name': 'admin_dashboard:assign_zones'},
            {'title': 'Manage Transfers', 'icon': 'fas fa-exchange-alt', 'url_name': 'admin_dashboard:manage_transfers'},
            {'title': 'Manage Players', 'icon': 'fas fa-users', 'url_name': 'teams:admin_manage_players'},
            {'title': 'Team Officials', 'icon': 'fas fa-id-card', 'url_name': 'teams:admin_manage_officials'},
        ]
    })
    sections.append({
        'title': 'Tournament Management',
        'icon': 'fas fa-trophy',
        'items': [
            {'title': 'Tournament Dashboard', 'icon': 'fas fa-trophy', 'url_name': 'tournaments:admin_dashboard'},
            {'title': 'Create Tournament', 'icon': 'fas fa-plus-circle', 'url_name': 'tournaments:create_tournament'},
        ]
    })
    sections.append({
        'title': 'Match Management',
        'icon': 'fas fa-futbol',
        'items': [
            {'title': 'Generate Fixtures', 'icon': 'fas fa-random', 'url_name': 'admin_dashboard:generate_fixtures_admin'},
            {'title': 'Reschedule Fixtures', 'icon': 'fas fa-calendar-alt', 'url_name': 'admin_dashboard:reschedule_fixtures_admin'},
            {'title': 'Manage Matches', 'icon': 'fas fa-edit', 'url_name': 'matches:manage_matches'},
            {'title': 'Appoint Officials', 'icon': 'fas fa-user-tie', 'url_name': 'referees:matches_needing_officials'},
        ]
    })
    sections.append({
        'title': 'Referee Management',
        'icon': 'fas fa-whistle',
        'items': [
            {'title': 'Pending Referees', 'icon': 'fas fa-user-clock', 'url_name': 'referees:pending_referees'},
            {'title': 'All Referees', 'icon': 'fas fa-list', 'url_name': 'referees:all_referees'},
            {'title': 'Pre-Match Forms Admin', 'icon': 'fas fa-file-signature', 'url_name': 'referees:pending_prematch_forms_admin'},
            {'title': 'Pre-Match Forms Manager', 'icon': 'fas fa-file-alt', 'url_name': 'referees:pending_prematch_forms_manager'},
        ]
    })
    sections.append({
        'title': 'Discipline & Reports',
        'icon': 'fas fa-gavel',
        'items': [
            {'title': 'Manage Suspensions', 'icon': 'fas fa-ban', 'url_name': 'admin_dashboard:view_suspensions'},
            {'title': 'Approve Match Reports', 'icon': 'fas fa-clipboard-check', 'url_name': 'referees:pending_reports'},
            {'title': 'Statistics Dashboard', 'icon': 'fas fa-chart-bar', 'url_name': 'admin_dashboard:statistics_dashboard'},
        ]
    })
    if user.is_superuser:
        sections.append({
            'title': 'System Admin',
            'icon': 'fas fa-server',
            'items': [
                {'title': 'Django Admin Panel', 'icon': 'fas fa-tools', 'url': '/admin/'},
            ]
        })

    for section in sections:
        section['items'] = _normalize_items(section['items'])

    return sections


def _build_footer_sections():
    return [
        {
            'title': 'Quick Links',
            'items': [
                {'title': 'Home', 'url_name': 'frontend:home'},
                {'title': 'Teams', 'url_name': 'teams:all_teams'},
                {'title': 'Fixtures', 'url_name': 'matches:fixtures'},
                {'title': 'Tables', 'url_name': 'matches:league_tables'},
                {'title': 'Top Scorers', 'url_name': 'matches:top_scorers'},
            ]
        },
        {
            'title': 'Registration',
            'items': [
                {'title': 'Register Team', 'url_name': 'teams:team_registration'},
                {'title': 'Become a Referee', 'url_name': 'referees:referee_registration'},
                {'title': 'League Rules', 'url_name': 'frontend:rules'},
                {'title': 'About Us', 'url_name': 'frontend:about'},
                {'title': 'Contact', 'url_name': 'frontend:contact'},
            ]
        },
    ]


def _build_social_links():
    return [
        {'title': 'Facebook', 'icon': 'fab fa-facebook fa-lg', 'url': '#'},
        {'title': 'Twitter', 'icon': 'fab fa-twitter fa-lg', 'url': '#'},
        {'title': 'Instagram', 'icon': 'fab fa-instagram fa-lg', 'url': '#'},
        {'title': 'YouTube', 'icon': 'fab fa-youtube fa-lg', 'url': '#'},
    ]


@register.simple_tag(takes_context=True)
def site_top_nav(context):
    user = context.get('user') or getattr(context.get('request', None), 'user', None)
    request = context.get('request')
    path = getattr(request, 'path', '') if request else ''
    items = _build_site_nav(user)
    return _normalize_items(items, path)


@register.simple_tag(takes_context=True)
def admin_dropdown(context):
    user = context.get('user') or getattr(context.get('request', None), 'user', None)
    return _build_admin_dropdown(user)


@register.simple_tag
def footer_sections():
    sections = _build_footer_sections()
    for section in sections:
        section['items'] = _normalize_items(section['items'])
    return sections


@register.simple_tag
def social_links():
    return _build_social_links()


@register.simple_tag(takes_context=True)
def dashboard_nav(context):
    user = context.get('user') or getattr(context.get('request', None), 'user', None)
    request = context.get('request')
    path = getattr(request, 'path', '') if request else ''

    sections = []
    sections.append({
        'title': 'Main',
        'items': [
            {
                'title': 'Dashboard',
                'icon': 'fas fa-tachometer-alt',
                'url_name': 'dashboard',
            }
        ]
    })

    if user and (user.is_staff or user.is_superuser):
        sections.append({
            'title': 'League',
            'items': [
                {'title': 'Teams', 'icon': 'fas fa-users', 'url_name': 'teams:dashboard'},
                {'title': 'Players', 'icon': 'fas fa-user-friends', 'url_name': 'teams:admin_manage_players'},
                {'title': 'Team Officials', 'icon': 'fas fa-user-tie', 'url_name': 'teams:admin_manage_officials'},
                {'title': 'Transfers', 'icon': 'fas fa-exchange-alt', 'url_name': 'admin_dashboard:manage_transfers'},
                {'title': 'Approve Teams', 'icon': 'fas fa-user-check', 'url_name': 'admin_dashboard:approve_registrations'},
            ]
        })
        sections.append({
            'title': 'Matches',
            'items': [
                {'title': 'Manage Matches', 'icon': 'fas fa-futbol', 'url_name': 'matches:manage_matches'},
                {'title': 'Generate Fixtures', 'icon': 'fas fa-calendar-plus', 'url_name': 'admin_dashboard:generate_fixtures_admin'},
                {'title': 'Reschedule', 'icon': 'fas fa-calendar-alt', 'url_name': 'admin_dashboard:reschedule_fixtures_admin'},
                {'title': 'Appoint Officials', 'icon': 'fas fa-user-check', 'url_name': 'referees:matches_needing_officials'},
            ]
        })
        sections.append({
            'title': 'Referees',
            'items': [
                {'title': 'Referee Dashboard', 'icon': 'fas fa-whistle', 'url_name': 'referees:referee_dashboard'},
                {'title': 'All Referees', 'icon': 'fas fa-list-ul', 'url_name': 'referees:all_referees'},
                {'title': 'Pending Approvals', 'icon': 'fas fa-user-clock', 'url_name': 'referees:pending_referees'},
                {'title': 'Pre-Match Forms', 'icon': 'fas fa-file-signature', 'url_name': 'referees:pending_prematch_forms_admin'},
            ]
        })
        sections.append({
            'title': 'Reports',
            'items': [
                {'title': 'Statistics', 'icon': 'fas fa-chart-bar', 'url_name': 'admin_dashboard:statistics_dashboard'},
                {'title': 'Match Reports', 'icon': 'fas fa-file-alt', 'url_name': 'admin_dashboard:approve_reports'},
                {'title': 'Suspensions', 'icon': 'fas fa-ban', 'url_name': 'admin_dashboard:view_suspensions'},
                {'title': 'Activity Log', 'icon': 'fas fa-history', 'url_name': 'admin_dashboard:activity_logs'},
            ]
        })
        sections.append({
            'title': 'Tournaments',
            'items': [
                {'title': 'Tournaments', 'icon': 'fas fa-trophy', 'url_name': 'tournaments:admin_dashboard'},
                {'title': 'Create Tournament', 'icon': 'fas fa-plus-circle', 'url_name': 'tournaments:create_tournament'},
            ]
        })
        if user.is_superuser:
            sections.append({
                'title': 'System',
                'items': [
                    {'title': 'User Management', 'icon': 'fas fa-users-cog', 'url_name': 'admin_dashboard:manage_league_admins'},
                    {'title': 'Django Admin', 'icon': 'fas fa-tools', 'url': '/admin/', 'danger': False},
                ]
            })

    if user and _user_in_group(user, 'Team Managers'):
        sections.append({
            'title': 'My Team',
            'items': [
                {'title': 'Team Overview', 'icon': 'fas fa-shield-alt', 'url_name': 'dashboard'},
                {'title': 'Add Players', 'icon': 'fas fa-user-plus', 'url': '/teams/add-players-approved/'},
                {'title': 'Officials', 'icon': 'fas fa-user-tie', 'url_name': 'teams:team_officials'},
                {'title': 'Kit Colors', 'icon': 'fas fa-tshirt', 'url_name': 'teams:select_kit_colors'},
                {'title': 'Transfer Search', 'icon': 'fas fa-exchange-alt', 'url_name': 'teams:search_players'},
                {'title': 'My Transfers', 'icon': 'fas fa-paper-plane', 'url_name': 'teams:my_transfer_requests'},
            ]
        })

    if user and _user_in_group(user, 'Referees'):
        sections.append({
            'title': 'Officiating',
            'items': [
                {'title': 'My Dashboard', 'icon': 'fas fa-whistle', 'url_name': 'dashboard'},
                {'title': 'Availability', 'icon': 'fas fa-calendar-check', 'url_name': 'referees:referee_availability'},
                {'title': 'My Profile', 'icon': 'fas fa-id-card', 'url_name': 'referees:referee_profile'},
            ]
        })

    sections.append({
        'title': 'Public',
        'items': [
            {'title': 'League Tables', 'icon': 'fas fa-table', 'url_name': 'matches:league_tables'},
            {'title': 'Fixtures', 'icon': 'fas fa-calendar', 'url_name': 'matches:fixtures'},
            {'title': 'All Tournaments', 'icon': 'fas fa-globe', 'url_name': 'tournaments:tournament_list'},
        ]
    })

    for section in sections:
        section['items'] = _normalize_items(section['items'], path)

    return sections
