"""
fkf_league/templatetags/fkf_tags.py

Shared template tags that replace repeated HTML if/elif chains across the project.

Usage in any template:
    {% load fkf_tags %}
"""
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


# ── Status badges ─────────────────────────────────────────────────────────

# Maps status string → (Bootstrap bg class, display label)
_SQUAD_STATUS = {
    'pending':   ('bg-secondary',         'Not Submitted'),
    'submitted': ('bg-warning text-dark',  'Awaiting Approval'),
    'approved':  ('bg-success',            'Approved'),
    'locked':    ('bg-dark',               'Locked'),
    'rejected':  ('bg-danger',             'Rejected'),
}

_MATCH_STATUS = {
    'scheduled': ('bg-primary',           'Scheduled'),
    'live':      ('bg-danger',            'LIVE'),
    'ongoing':   ('bg-warning text-dark', 'Ongoing'),
    'completed': ('bg-success',           'Full Time'),
    'postponed': ('bg-secondary',         'Postponed'),
    'cancelled': ('bg-dark',              'Cancelled'),
}

_TRANSFER_STATUS = {
    'pending_parent': ('bg-warning text-dark', 'Awaiting Decision'),
    'approved':       ('bg-success',           'Approved'),
    'rejected':       ('bg-danger',            'Rejected'),
    'cancelled':      ('bg-secondary',         'Cancelled'),
}

_REG_STATUS = {
    'pending':  ('bg-warning text-dark', 'Pending'),
    'approved': ('bg-success',           'Approved'),
    'rejected': ('bg-danger',            'Rejected'),
}

_TEAM_STATUS = {
    'pending':   ('bg-warning text-dark', 'Pending'),
    'approved':  ('bg-success',           'Approved'),
    'rejected':  ('bg-danger',            'Rejected'),
    'suspended': ('bg-dark',              'Suspended'),
}

_REFEREE_STATUS = {
    'pending':   ('bg-warning text-dark', 'Pending'),
    'approved':  ('bg-success',           'Active'),
    'rejected':  ('bg-danger',            'Rejected'),
    'suspended': ('bg-dark',              'Suspended'),
}


def _badge(status, mapping, default_label=None):
    cls, label = mapping.get(status, ('bg-secondary', default_label or status.title()))
    return format_html('<span class="badge {}">{}</span>', cls, label)


@register.simple_tag
def squad_badge(status):
    """{% squad_badge squad.status %}"""
    return _badge(status, _SQUAD_STATUS)


@register.simple_tag
def match_badge(status):
    """{% match_badge match.status %}"""
    return _badge(status, _MATCH_STATUS)


@register.simple_tag
def transfer_badge(status):
    """{% transfer_badge transfer.status %}"""
    return _badge(status, _TRANSFER_STATUS)


@register.simple_tag
def reg_badge(status):
    """{% reg_badge registration.status %} — for tournament/team registrations"""
    return _badge(status, _REG_STATUS)


@register.simple_tag
def team_badge(status):
    """{% team_badge team.status %}"""
    return _badge(status, _TEAM_STATUS)


@register.simple_tag
def referee_badge(status):
    """{% referee_badge referee.status %}"""
    return _badge(status, _REFEREE_STATUS)


# ── Form badges (W/D/L) ───────────────────────────────────────────────────

_FORM_CLASSES = {'W': 'form-w', 'D': 'form-d', 'L': 'form-l'}
_FORM_TITLES  = {'W': 'Win',    'D': 'Draw',   'L': 'Loss'}

@register.simple_tag
def form_badge(result):
    """
    {% form_badge result %}
    Renders a single W/D/L form badge.
    Replaces 6-line if/elif in league_tables.html and any table showing form.
    """
    css   = _FORM_CLASSES.get(result, 'bg-secondary')
    title = _FORM_TITLES.get(result, result)
    return format_html('<span class="form-badge {}" title="{}">{}</span>', css, title, result)


@register.simple_tag
def form_string(form):
    """
    {% form_string entry.form %}
    Renders an entire form string like 'WWDLW' as a row of badges.
    """
    if not form:
        return mark_safe('<span class="text-muted" style="font-size:.78rem;">—</span>')
    parts = [
        format_html('<span class="form-badge {}" title="{}">{}</span>',
                    _FORM_CLASSES.get(r, 'bg-secondary'),
                    _FORM_TITLES.get(r, r),
                    r)
        for r in form
    ]
    return mark_safe('<div class="d-flex gap-1">' + ''.join(parts) + '</div>')


# ── Registration window card ──────────────────────────────────────────────

@register.inclusion_tag('partials/_reg_window_card.html')
def reg_window_card(label, icon, is_open, deadline, closed_date):
    """
    {% reg_window_card "Player Registration" "fas fa-user-plus"
        league_settings.player_registration_open
        league_settings.player_registration_deadline
        league_settings.player_registration_closed_date %}

    Replaces the 20-line repeated card block in team_manager.html and home.html.
    """
    return {
        'label':       label,
        'icon':        icon,
        'is_open':     is_open,
        'deadline':    deadline,
        'closed_date': closed_date,
    }


# ── Empty state ──────────────────────────────────────────────────────────

@register.inclusion_tag('partials/_empty_state.html')
def empty_state(icon='inbox', color='muted', title='No items', message=''):
    """
    {% empty_state icon="calendar-times" color="muted"
                   title="No Fixtures" message="Fixtures will appear here." %}
    """
    return {'icon': icon, 'color': color, 'title': title, 'message': message}


# ── Table card wrapper ────────────────────────────────────────────────────

@register.inclusion_tag('partials/_table_card.html', takes_context=True)
def table_card(context, title, icon='', gradient='', badge_count=None):
    """
    {% table_card "All Players" icon="fas fa-users" gradient="blue" badge_count=total %}
        ... table content via slot (nested block)
    {% end_table_card %}
    NOTE: use {% include 'partials/_table_card.html' with ... %} for full content.
    """
    return {
        'title':       title,
        'icon':        icon,
        'gradient':    gradient,
        'badge_count': badge_count,
    }


# ── User role display ─────────────────────────────────────────────────────

@register.simple_tag(takes_context=True)
def user_role(context):
    """
    {% user_role %}
    Returns the display label for the current user's role.
    Replaces the 5-line if/elif in base_dashboard.html and manage_league_admins.html.
    """
    user = context.get('user')
    if not user or not user.is_authenticated:
        return 'Guest'
    if user.is_superuser:
        return 'Super Admin'
    if user.is_staff:
        return 'League Admin'
    groups = list(user.groups.values_list('name', flat=True))
    return groups[0] if groups else 'Member'


# ── Can-manage permission tag ─────────────────────────────────────────────

@register.simple_tag(takes_context=True)
def can_manage(context):
    """
    {% can_manage as is_admin %}
    Returns True if current user is staff/superuser or in an admin group.
    Replaces inline permission checks in tournament templates.
    """
    user = context.get('user')
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.groups.filter(
        name__in=['League Admin', 'League Manager', 'Referees Manager']
    ).exists()


# ── Card header gradient helper ───────────────────────────────────────────

_GRADIENT_MAP = {
    'red':    'background:linear-gradient(90deg,#e63946,#c1121f)',
    'green':  'background:linear-gradient(90deg,#2dc653,#198754)',
    'blue':   'background:linear-gradient(90deg,#4361ee,#3a0ca3)',
    'orange': 'background:linear-gradient(90deg,#f4a261,#e76f51)',
    'dark':   'background:linear-gradient(90deg,#1a1a2e,#2d3748)',
    'teal':   'background:linear-gradient(90deg,#0077b6,#023e8a)',
    'purple': 'background:linear-gradient(90deg,#7209b7,#560bad)',
}

@register.simple_tag
def card_header_style(color='dark'):
    """
    {% card_header_style "green" %}
    Returns the inline style string for a coloured card header.
    Removes repetitive inline gradients from every card-header across all templates.
    """
    return mark_safe(_GRADIENT_MAP.get(color, _GRADIENT_MAP['dark']) + ';color:white;padding:1rem 1.5rem;')


# ── Urgency level for match appointment deadlines ─────────────────────────

@register.simple_tag
def appointment_urgency_badge(days_left):
    """
    {% appointment_urgency_badge days_left %}
    Returns a coloured badge for how urgently officials need to be appointed.
    Replaces inline {% if days_left <= 1 %}bg-danger{% elif %}... in referees templates.
    """
    try:
        d = int(days_left)
    except (TypeError, ValueError):
        return format_html('<span class="badge bg-secondary">—</span>')
    if d <= 1:
        cls, label = 'bg-danger',           f'{d} day{"s" if d != 1 else ""} — URGENT'
    elif d <= 3:
        cls, label = 'bg-warning text-dark', f'{d} days'
    else:
        cls, label = 'bg-info',              f'{d} days'
    return format_html('<span class="badge {}">{}</span>', cls, label)
