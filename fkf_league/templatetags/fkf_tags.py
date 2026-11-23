"""
fkf_league/templatetags/fkf_tags.py

Shared presentation helpers (status badges, form pills, registration-window card,
empty state, role label). Registered globally via TEMPLATES ``libraries`` because
``fkf_league`` is the project package, not an installed app:

    {% load fkf_tags %}

All HTML is produced with ``format_html``/``format_html_join`` or templates, so
values are always escaped. Badge markup follows the design system's
``status-badge`` component (see docs/design-system.md).
"""
from __future__ import annotations

from typing import Any

from django import template
from django.utils.html import format_html, format_html_join
from django.utils.safestring import SafeString

from fkf_league.permissions import role_label

register = template.Library()


# ── Status badges ─────────────────────────────────────────────────────────
# status value → (tone, label). Tones map to .status-<tone> in app.css:
# neutral | accent | success | warning | danger | dark

_SQUAD_STATUS = {
    'pending':   ('neutral', 'Not Submitted'),
    'submitted': ('warning', 'Awaiting Approval'),
    'approved':  ('success', 'Approved'),
    'locked':    ('dark',    'Locked'),
    'rejected':  ('danger',  'Rejected'),
}

_MATCH_STATUS = {
    'scheduled': ('neutral', 'Scheduled'),
    'live':      ('accent',  'LIVE'),
    'ongoing':   ('accent',  'Ongoing'),
    'completed': ('success', 'Full Time'),
    'postponed': ('warning', 'Postponed'),
    'cancelled': ('dark',    'Cancelled'),
}

_TRANSFER_STATUS = {
    'pending_parent': ('warning', 'Awaiting Decision'),
    'approved':       ('success', 'Approved'),
    'rejected':       ('danger',  'Rejected'),
    'cancelled':      ('neutral', 'Cancelled'),
}

_REG_STATUS = {
    'pending':  ('warning', 'Pending'),
    'approved': ('success', 'Approved'),
    'rejected': ('danger',  'Rejected'),
}

_TEAM_STATUS = {
    'pending':   ('warning', 'Pending'),
    'approved':  ('success', 'Approved'),
    'rejected':  ('danger',  'Rejected'),
    'suspended': ('dark',    'Suspended'),
}

_REFEREE_STATUS = {
    'pending':   ('warning', 'Pending'),
    'approved':  ('success', 'Active'),
    'rejected':  ('danger',  'Rejected'),
    'suspended': ('dark',    'Suspended'),
}


def _badge(status: Any, mapping: dict[str, tuple[str, str]]) -> SafeString:
    key = '' if status is None else str(status)
    tone, label = mapping.get(key, ('neutral', key.replace('_', ' ').title() or '—'))
    return format_html('<span class="badge status-badge status-{}">{}</span>', tone, label)


@register.simple_tag
def squad_badge(status: Any) -> SafeString:
    """{% squad_badge squad.status %}"""
    return _badge(status, _SQUAD_STATUS)


@register.simple_tag
def match_badge(status: Any) -> SafeString:
    """{% match_badge match.status %}"""
    return _badge(status, _MATCH_STATUS)


@register.simple_tag
def transfer_badge(status: Any) -> SafeString:
    """{% transfer_badge transfer.status %}"""
    return _badge(status, _TRANSFER_STATUS)


@register.simple_tag
def reg_badge(status: Any) -> SafeString:
    """{% reg_badge registration.status %} — tournament/team registrations."""
    return _badge(status, _REG_STATUS)


@register.simple_tag
def team_badge(status: Any) -> SafeString:
    """{% team_badge team.status %}"""
    return _badge(status, _TEAM_STATUS)


@register.simple_tag
def referee_badge(status: Any) -> SafeString:
    """{% referee_badge referee.status %}"""
    return _badge(status, _REFEREE_STATUS)


# ── Form pills (W/D/L) ────────────────────────────────────────────────────

_FORM = {'W': ('form-w', 'Win'), 'D': ('form-d', 'Draw'), 'L': ('form-l', 'Loss')}


def _form_args(result: str) -> tuple[str, str, str]:
    css, title = _FORM.get(result, ('form-n', result))
    return css, title, result


@register.simple_tag
def form_badge(result: str) -> SafeString:
    """{% form_badge "W" %} — a single W/D/L pill."""
    return format_html('<span class="form-badge {}" title="{}">{}</span>', *_form_args(result))


@register.simple_tag
def form_string(form: str | None) -> SafeString:
    """{% form_string entry.form %} — renders e.g. 'WWDLW' as a row of pills."""
    if not form:
        return format_html('<span class="text-body-secondary small">{}</span>', '—')
    pills = format_html_join(
        '', '<span class="form-badge {}" title="{}">{}</span>',
        (_form_args(r) for r in str(form)),
    )
    return format_html('<span class="form-pills">{}</span>', pills)


# ── Inclusion components ──────────────────────────────────────────────────

@register.inclusion_tag('partials/_reg_window_card.html')
def reg_window_card(label: str, icon: str, is_open: bool, deadline: Any, closed_date: Any) -> dict:
    """
    {% reg_window_card "Player Registration" "fas fa-user-plus"
        league_settings.player_registration_open
        league_settings.player_registration_deadline
        league_settings.player_registration_closed_date %}
    """
    return {
        'label': label,
        'icon': icon,
        'is_open': is_open,
        'deadline': deadline,
        'closed_date': closed_date,
    }


@register.inclusion_tag('partials/_empty_state.html')
def empty_state(icon: str = 'inbox', color: str = 'muted', title: str = 'No items', message: str = '') -> dict:
    """
    {% empty_state icon="calendar-times" title="No fixtures" message="Fixtures will appear here." %}
    ``icon`` is a Font Awesome name without the ``fa-`` prefix.
    """
    return {'icon': icon, 'color': color, 'title': title, 'message': message}


# ── Role label ────────────────────────────────────────────────────────────

@register.simple_tag(takes_context=True)
def user_role(context: template.Context) -> str:
    """{% user_role %} — display label for the current user's role."""
    return role_label(context.get('user'))
