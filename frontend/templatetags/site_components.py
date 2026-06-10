from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse, NoReverseMatch
from .site_navigation import (
    _build_site_nav,
    _build_admin_dropdown,
    _build_footer_sections,
    _build_social_links,
    _normalize_items,
    _user_in_group,
)

register = template.Library()

HOME_FEATURE_CARDS = [
    {
        'title': 'Team Management',
        'icon': 'fas fa-futbol',
        'description': 'Register your team, manage players, and track performance throughout the season.',
        'url_name': 'teams:team_registration',
        'color_class': 'stat-gradient-blue',
        'button_text': 'Register Team',
    },
    {
        'title': 'League Standings',
        'icon': 'fas fa-trophy',
        'description': 'View real-time league tables, match results, and zone rankings.',
        'url_name': 'matches:league_tables',
        'color_class': 'stat-gradient-orange',
        'button_text': 'View Tables',
    },
    {
        'title': 'Match Fixtures',
        'icon': 'fas fa-calendar-alt',
        'description': 'Check upcoming fixtures, match schedules, and venue information.',
        'url_name': 'matches:fixtures',
        'color_class': 'stat-gradient-green',
        'button_text': 'View Fixtures',
    },
    {
        'title': 'Statistics & Rankings',
        'icon': 'fas fa-chart-line',
        'description': 'Track top scorers, player stats, and team performance metrics.',
        'url_name': 'matches:top_scorers',
        'color_class': 'stat-gradient-red',
        'button_text': 'View Stats',
    },
]

HOME_NEWS_ITEMS = [
    {
        'title': 'Registration Open',
        'subtitle': 'Now',
        'description': 'Team registration for 2025/2026 season is now open.',
        'url_name': 'teams:team_registration',
        'badge_class': 'bg-success-subtle text-success',
    },
    {
        'title': 'Fixtures Released',
        'subtitle': 'Soon',
        'description': 'First round fixtures have been published for managers and referees.',
        'url_name': 'matches:fixtures',
        'badge_class': 'bg-warning-subtle text-warning',
    },
    {
        'title': 'Referee Registration',
        'subtitle': 'Now',
        'description': 'Referee registration is live, and officials can complete their profiles.',
        'url_name': 'referees:referee_registration',
        'badge_class': 'bg-success-subtle text-success',
    },
]

HOME_QUICK_LINKS = [
    {'title': 'Top Scorers', 'url_name': 'matches:top_scorers', 'icon': 'fas fa-futbol text-primary'},
    {'title': 'Become a Referee', 'url_name': 'referees:referee_registration', 'icon': 'fas fa-whistle text-success'},
    {'title': 'League Rules', 'url_name': 'frontend:rules', 'icon': 'fas fa-book text-danger'},
    {'title': 'Contact Us', 'url_name': 'frontend:contact', 'icon': 'fas fa-envelope text-warning'},
]


def _get_url_for_item(item):
    try:
        if item.get('url_name'):
            return reverse(item['url_name'])
        return item.get('url', '#')
    except (NoReverseMatch, TypeError, KeyError):
        return item.get('url', '#')


def _message_icon(tag):
    return {
        'error': 'exclamation-circle',
        'success': 'check-circle',
        'warning': 'exclamation-triangle',
    }.get(tag, 'info-circle')


def _render_nav_link(item):
    active = ' active' if item.get('is_active') else ''
    icon_html = format_html('<i class="{}"></i> ', item['icon']) if item.get('icon') else ''
    return format_html(
        '<li class="nav-item"><a class="nav-link{}" href="{}">{}{}</a></li>',
        active,
        item.get('url', '#'),
        icon_html,
        item.get('title', ''),
    )


@register.simple_tag(takes_context=True)
def render_site_nav(context):
    user = context.get('user') or getattr(context.get('request', None), 'user', None)
    request = context.get('request')
    path = getattr(request, 'path', '') if request else ''
    items = _normalize_items(_build_site_nav(user), path)

    html = ['<ul class="navbar-nav ms-auto">']
    for item in items:
        html.append(_render_nav_link(item))

    if user and user.is_authenticated and user.is_staff:
        admin_sections = _build_admin_dropdown(user)
        if admin_sections:
            html.append('<li class="nav-item dropdown">')
            html.append(
                '<a class="nav-link dropdown-toggle" href="#" id="adminDropdown" role="button" '
                'data-bs-toggle="dropdown" aria-expanded="false"><i class="fas fa-user-shield"></i> Admin Panel</a>'
            )
            html.append('<ul class="dropdown-menu dropdown-menu-end" aria-labelledby="adminDropdown" style="min-width: 280px;">')
            for section in admin_sections:
                html.append(format_html(
                    '<li class="dropdown-header"><i class="{}"></i> {}</li>',
                    section['icon'],
                    section['title'],
                ))
                for item in section['items']:
                    html.append(format_html(
                        '<li><a class="dropdown-item" href="{}"><i class="{}"></i> {}</a></li>',
                        item.get('url', '#'),
                        item.get('icon', ''),
                        item.get('title', ''),
                    ))
                if section is not admin_sections[-1]:
                    html.append('<li><hr class="dropdown-divider"></li>')
            html.append('</ul></li>')

    html.append('</ul>')
    return mark_safe(''.join(html))


@register.simple_tag
def render_footer():
    sections = _build_footer_sections()
    for section in sections:
        section['items'] = _normalize_items(section['items'])

    social_links = _build_social_links()
    html = ['<footer class="footer-custom">', '<div class="container py-5">', '<div class="row g-4">']
    html.append(
        '<div class="col-lg-4 col-md-6"><h5 class="text-white mb-3"><i class="fas fa-futbol me-2"></i>FKF Meru County League</h5>'
        '<p class="text-white-50">Official Football Kenya Federation Meru County League Management System. '
        'Promoting grassroots football development and competitive excellence in Meru County.</p>'
        '<div class="social-links mt-3">'
    )
    for social in social_links:
        html.append(format_html(
            '<a href="{}" class="text-white me-3" title="{}"><i class="{}"></i></a>',
            social.get('url', '#'),
            social['title'],
            social['icon'],
        ))
    html.append('</div></div>')

    for section in sections:
        html.append('<div class="col-lg-2 col-md-6"><h6 class="text-white mb-3">{}</h6><ul class="list-unstyled footer-links">'.format(section['title']))
        for item in section['items']:
            html.append(format_html(
                '<li><a href="{}"><i class="fas fa-chevron-right me-2"></i>{}</a></li>',
                item.get('url', '#'),
                item['title'],
            ))
        html.append('</ul></div>')

    html.append(
        '<div class="col-lg-3 col-md-6"><h6 class="text-white mb-3">Contact Us</h6>'
        '<ul class="list-unstyled text-white-50">'
        '<li class="mb-2"><i class="fas fa-map-marker-alt me-2"></i>Meru County, Kenya</li>'
        '<li class="mb-2"><i class="fas fa-phone me-2"></i>+254 XXX XXX XXX</li>'
        '<li class="mb-2"><i class="fas fa-envelope me-2"></i>info@fkfmeru.co.ke</li>'
        '<li class="mb-2"><i class="fas fa-clock me-2"></i>Mon - Fri: 9AM - 5PM</li>'
        '</ul></div>'
    )
    html.append('</div>')
    html.append(
        '<hr class="bg-white-50 my-4">'
        '<div class="row"><div class="col-md-6 text-center text-md-start">'
        '<p class="mb-0" style="color: rgba(255,255,255,0.7);">&copy; 2026 FKF Meru County League. All rights reserved.</p>'
        '</div><div class="col-md-6 text-center text-md-end">'
        '<p class="mb-0" style="color: rgba(255,255,255,0.7);">Powered by Emmanuel Technology Services</p>'
        '<p class="mb-0 fst-italic" style="color: rgba(255,255,255,0.6); font-size: 0.9em;">Code the Future</p>'
        '</div></div>'
    )
    html.append('</div></footer>')

    return mark_safe(''.join(html))


@register.simple_tag(takes_context=True)
def render_messages(context):
    messages = context.get('messages')
    if not messages:
        return ''

    html = ['<div class="messages-container mb-4">']
    for message in messages:
        icon = _message_icon(message.tags)
        html.append(format_html(
            '<div class="alert alert-{} alert-dismissible fade show" role="alert">'
            '<i class="fas fa-{} me-2"></i>{}'
            '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>'
            '</div>',
            message.tags,
            icon,
            message,
        ))
    html.append('</div>')
    return mark_safe(''.join(html))


@register.simple_tag(takes_context=True)
def render_home_page(context):
    league_settings = context.get('league_settings')
    total_teams = context.get('total_teams', 0)
    completed_matches = context.get('completed_matches', 0)

    def _build_deadline_section(name, icon, is_open, deadline, closed_date):
        status = 'OPEN' if is_open else 'CLOSED'
        badge = 'bg-success' if is_open else 'bg-danger'
        result = [
            '<div class="mb-3 pb-3 border-bottom">',
            '<div class="d-flex justify-content-between align-items-center mb-1">',
            f'<span class="fw-semibold small"><i class="{icon} me-1"></i> {name}</span>',
            f'<span class="badge {badge}">{status}</span>',
            '</div>',
        ]
        if is_open and deadline:
            result.append(f'<div class="text-muted" style="font-size:0.8rem;">Closes: {deadline.strftime("%b %d, %Y %H:%M")}</div>')
            result.append(f'<div class="countdown-small" data-deadline="{deadline.isoformat()}"></div>')
        elif not is_open and closed_date:
            result.append(f'<div class="text-muted" style="font-size:0.8rem;">Closed: {closed_date.strftime("%b %d, %Y %H:%M")}</div>')
        result.append('</div>')
        return ''.join(result)

    hero = [
        '<div class="home-hero" data-aos="fade-down">',
        '<div class="hero-content">',
        '<div class="hero-badge"><i class="fas fa-futbol me-1"></i> FKF Meru County — Official Platform</div>',
        '<h1 class="hero-title">FKF Meru County<br>League Management</h1>',
        '<p class="hero-subtitle">Register your team, manage matches, track statistics, and follow league standings — all in one place.</p>',
        '<div class="hero-actions">',
    ]
    for card in HOME_FEATURE_CARDS[:3]:
        hero.append(format_html(
            '<a href="{}" class="btn btn-lg hero-button">{}<span>{}</span></a>',
            _get_url_for_item(card),
            format_html('<i class="{} me-2"></i>', card['icon']),
            card['button_text'],
        ))
    hero.append('</div></div></div>')

    feature_cards = ['<div class="row g-3 mb-4" data-aos="fade-up">']
    for card in HOME_FEATURE_CARDS:
        feature_cards.append(format_html(
            '<div class="col-sm-6"><div class="feature-card p-4">'
            '<div class="feature-card-icon {}"><i class="{}"></i></div>'
            '<h5 class="fw-bold mb-2">{}</h5>'
            '<p class="text-muted small mb-3">{}</p>'
            '<a href="{}" class="btn btn-sm feature-button"><i class="fas fa-arrow-right me-1"></i> {}</a>'
            '</div></div>',
            card['color_class'],
            card['icon'],
            card['title'],
            card['description'],
            _get_url_for_item(card),
            card['button_text'],
        ))
    feature_cards.append('</div>')

    news_rows = ['<div class="list-group list-group-flush">']
    for item in HOME_NEWS_ITEMS:
        news_rows.append(format_html(
            '<a href="{}" class="list-group-item list-group-item-action border-0 py-3">'
            '<div class="d-flex justify-content-between mb-1"><span class="fw-semibold small">{}</span>'
            '<span class="badge {}" style="font-size:0.7rem;">{}</span></div>'
            '<p class="text-muted mb-0" style="font-size:0.82rem;">{}</p></a>',
            _get_url_for_item(item),
            item['title'],
            item['badge_class'],
            item['subtitle'],
            item['description'],
        ))
    news_rows.append('</div>')

    quick_links = ['<div class="list-group list-group-flush">']
    for link in HOME_QUICK_LINKS:
        quick_links.append(format_html(
            '<a href="{}" class="list-group-item list-group-item-action border-0 py-3">'
            '<i class="{} me-2"></i> {}</a>',
            _get_url_for_item(link),
            link['icon'],
            link['title'],
        ))
    quick_links.append('</div>')

    html = [
        '<div class="row g-4">',
        '<div class="col-lg-8">',
        *hero,
        *feature_cards,
        '</div>',
        '<div class="col-lg-4">',
    ]

    if league_settings:
        html.append('<div class="sidebar-card" data-aos="fade-left">')
        html.append('<div class="sidebar-header sidebar-header-deadline"><h6 class="mb-0 fw-bold"><i class="fas fa-clock me-2"></i>Registration Deadlines</h6></div><div class="p-3">')
        html.append(_build_deadline_section(
            'Team Registration',
            'fas fa-users text-primary',
            getattr(league_settings, 'team_registration_open', False),
            getattr(league_settings, 'team_registration_deadline', None),
            getattr(league_settings, 'team_registration_closed_date', None),
        ))
        html.append(_build_deadline_section(
            'Player Registration',
            'fas fa-user-plus text-success',
            getattr(league_settings, 'player_registration_open', False),
            getattr(league_settings, 'player_registration_deadline', None),
            getattr(league_settings, 'player_registration_closed_date', None),
        ))
        html.append(_build_deadline_section(
            'Transfer Window',
            'fas fa-exchange-alt text-info',
            getattr(league_settings, 'transfer_window_open', False),
            getattr(league_settings, 'transfer_window_deadline', None),
            getattr(league_settings, 'transfer_window_closed_date', None),
        ))
        html.append('</div></div>')

    html.append('<div class="sidebar-card" data-aos="fade-left" data-aos-delay="100"><div class="sidebar-header sidebar-header-stats"><h6 class="mb-0 fw-bold"><i class="fas fa-chart-bar me-2"></i>Quick Stats</h6></div><div class="p-3"><div class="row text-center g-2">')
    html.append(format_html(
        '<div class="col-6"><div class="stat-box"><div class="stat-num text-primary">{}</div><div class="text-muted small">Teams</div></div></div>',
        total_teams,
    ))
    html.append(format_html(
        '<div class="col-6"><div class="stat-box"><div class="stat-num text-success">{}</div><div class="text-muted small">Matches Played</div></div></div>',
        completed_matches,
    ))
    html.append('</div></div></div>')

    html.append('<div class="sidebar-card" data-aos="fade-left" data-aos-delay="150"><div class="sidebar-header sidebar-header-news"><h6 class="mb-0 fw-bold"><i class="fas fa-newspaper me-2"></i>Latest News</h6></div>')
    html.extend(news_rows)
    html.append('</div>')
    html.append('<div class="sidebar-card" data-aos="fade-left" data-aos-delay="200"><div class="sidebar-header sidebar-header-links"><h6 class="mb-0 fw-bold"><i class="fas fa-bolt me-2"></i>Quick Links</h6></div>')
    html.extend(quick_links)
    html.append('</div>')

    html.append('</div></div>')
    return mark_safe(''.join(html))


def _get_user_role(user):
    if not user:
        return 'Guest'
    if user.is_superuser:
        return 'Super Admin'
    if user.is_staff:
        return 'League Admin'
    groups = user.groups.all()
    return groups[0].name if groups else 'Member'


@register.simple_tag(takes_context=True)
def render_dashboard_sidebar(context):
    user = context.get('user') or getattr(context.get('request', None), 'user', None)
    request = context.get('request')
    path = getattr(request, 'path', '') if request else ''

    sections = [
        {
            'title': 'Main',
            'items': [
                {'title': 'Dashboard', 'icon': 'fas fa-tachometer-alt', 'url_name': 'dashboard'},
            ]
        }
    ]

    if user and (user.is_staff or user.is_superuser):
        sections.extend([
            {
                'title': 'League',
                'items': [
                    {'title': 'Teams', 'icon': 'fas fa-users', 'url_name': 'teams:dashboard'},
                    {'title': 'Players', 'icon': 'fas fa-user-friends', 'url_name': 'teams:admin_manage_players'},
                    {'title': 'Team Officials', 'icon': 'fas fa-user-tie', 'url_name': 'teams:admin_manage_officials'},
                    {'title': 'Transfers', 'icon': 'fas fa-exchange-alt', 'url_name': 'admin_dashboard:manage_transfers'},
                    {'title': 'Approve Teams', 'icon': 'fas fa-user-check', 'url_name': 'admin_dashboard:approve_registrations'},
                ]
            },
            {
                'title': 'Matches',
                'items': [
                    {'title': 'Manage Matches', 'icon': 'fas fa-futbol', 'url_name': 'matches:manage_matches'},
                    {'title': 'Generate Fixtures', 'icon': 'fas fa-calendar-plus', 'url_name': 'admin_dashboard:generate_fixtures_admin'},
                    {'title': 'Reschedule', 'icon': 'fas fa-calendar-alt', 'url_name': 'admin_dashboard:reschedule_fixtures_admin'},
                    {'title': 'Appoint Officials', 'icon': 'fas fa-user-check', 'url_name': 'referees:matches_needing_officials'},
                ]
            },
        ])

    if user and _user_in_group(user, 'Team Managers'):
        sections.append(
            {
                'title': 'My Team',
                'items': [
                    {'title': 'Team Overview', 'icon': 'fas fa-shield-alt', 'url_name': 'dashboard'},
                    {'title': 'Officials', 'icon': 'fas fa-user-tie', 'url_name': 'teams:team_officials'},
                    {'title': 'Kit Colors', 'icon': 'fas fa-tshirt', 'url_name': 'teams:select_kit_colors'},
                    {'title': 'Transfer Search', 'icon': 'fas fa-exchange-alt', 'url_name': 'teams:search_players'},
                ]
            }
        )

    if user and _user_in_group(user, 'Referees'):
        sections.append(
            {
                'title': 'Officiating',
                'items': [
                    {'title': 'My Dashboard', 'icon': 'fas fa-whistle', 'url_name': 'dashboard'},
                    {'title': 'Availability', 'icon': 'fas fa-calendar-check', 'url_name': 'referees:referee_availability'},
                    {'title': 'My Profile', 'icon': 'fas fa-id-card', 'url_name': 'referees:referee_profile'},
                ]
            }
        )

    sections.append(
        {
            'title': 'Public',
            'items': [
                {'title': 'League Tables', 'icon': 'fas fa-table', 'url_name': 'matches:league_tables'},
                {'title': 'Fixtures', 'icon': 'fas fa-calendar', 'url_name': 'matches:fixtures'},
                {'title': 'All Tournaments', 'icon': 'fas fa-globe', 'url_name': 'tournaments:tournament_list'},
            ]
        }
    )

    for section in sections:
        section['items'] = _normalize_items(section['items'], path)

    html = [
        '<div class="sb-brand">',
        '<a href="{}" class="sb-brand-link">'.format(reverse('frontend:home')),
        '<div class="sb-brand-icon"><i class="fas fa-futbol"></i></div>',
        '<div class="sb-brand-text"><span class="sb-brand-name">FKF Meru</span><span class="sb-brand-sub">County League</span></div>',
        '</a>',
        '<button class="sb-toggle-btn" id="sbToggleBtn" title="Collapse sidebar"><i class="fas fa-bars"></i></button>',
        '</div>',
    ]

    html.append('<div class="sb-user">')
    html.append(format_html(
        '<div class="sb-avatar">{}</div>'
        '<div class="sb-user-info"><span class="sb-user-name">{}</span>'
        '<span class="sb-user-role">{}</span></div>',
        (user.get_full_name() or user.username)[:1].upper() if user else 'G',
        user.get_full_name() or user.username if user else 'Guest',
        _get_user_role(user),
    ))
    html.append('</div>')

    html.append('<nav class="sb-nav">')
    for section in sections:
        html.append(format_html('<span class="sb-section-label">{}</span>', section['title']))
        for item in section['items']:
            classes = 'sb-nav-item'
            if item.get('is_active'):
                classes += ' active'
            if item.get('danger'):
                classes += ' danger'
            html.append(format_html(
                '<a href="{}" class="{}"><span class="nav-icon"><i class="{}"></i></span>'
                '<span class="nav-label">{}</span></a>',
                item.get('url', '#'),
                classes,
                item.get('icon', ''),
                item.get('title', ''),
            ))
    html.append('</nav>')

    return mark_safe(''.join(html))
