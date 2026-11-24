"""Team kit colours and images."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from fkf_league.permissions import is_league_admin_or_manager

from ..access import ensure_can_manage_team, get_managed_team
from ..forms import TeamKitForm
from ..models import Team

# (key, element-id prefix used by the page JS, title, section, default jersey/shorts/socks)
_KIT_CARDS = (
    ('home', 'home', 'Home kit', 'outfield', ('#c8102e', '#ffffff', '#c8102e')),
    ('away', 'away', 'Away kit', 'outfield', ('#ffffff', '#c8102e', '#ffffff')),
    ('third', 'third', 'Third kit', 'outfield', ('#6c757d', '#6c757d', '#6c757d')),
    ('gk_home', 'gkHome', 'GK home kit', 'goalkeeper', ('#00843d', '#00843d', '#00843d')),
    ('gk_away', 'gkAway', 'GK away kit', 'goalkeeper', ('#ffc107', '#ffc107', '#ffc107')),
    ('gk_third', 'gkThird', 'GK third kit', 'goalkeeper', ('#1f1f23', '#1f1f23', '#1f1f23')),
)


def _kit_cards(team):
    """One dict per kit for templates/teams/includes/_kit_card.html (presentation only)."""
    cards = []
    for key, js_id, title, section, defaults in _KIT_CARDS:
        cards.append({
            'key': key,
            'js_id': js_id,
            'title': title,
            'section': section,
            'required': key not in TeamKitForm.OPTIONAL_KITS,
            'image': getattr(team, f'{key}_kit_image'),
            'parts': [
                {'part': part, 'label': part.title(), 'name': f'{key}_{part}_color',
                 'value': getattr(team, f'{key}_{part}_color') or default}
                for part, default in zip(TeamKitForm.PARTS, defaults)
            ],
        })
    return cards


def _kit_editor(request, team, success_url):
    form = TeamKitForm(request.POST or None, request.FILES or None, instance=team)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Kit colors and images saved successfully!')
            return redirect(success_url)
        for error in form.non_field_errors():
            messages.error(request, error)
        for name, errors in form.errors.items():
            if name != '__all__':
                messages.error(request, f"{form.fields[name].label or name}: {' '.join(errors)}")
        team.refresh_from_db()  # don't render rejected values
    cards = _kit_cards(team)
    return render(request, 'teams/select_kit.html', {
        'form': form, 'team': team,
        'outfield_kits': [c for c in cards if c['section'] == 'outfield'],
        'goalkeeper_kits': [c for c in cards if c['section'] == 'goalkeeper'],
    })


@login_required
def select_kit_colors(request):
    """Onboarding step for a newly approved team's manager (then -> officials)."""
    team = get_managed_team(request.user)
    if not team:
        messages.error(request, "You are not assigned to any approved team.")
        return redirect('dashboard')
    return _kit_editor(request, team, 'teams:team_officials')


@login_required
def update_team_kits(request, team_id):
    """Edit kits of ``team_id`` — league staff for any team, a manager for their own."""
    team = get_object_or_404(Team, pk=team_id)
    ensure_can_manage_team(request.user, team)
    if team.status != Team.Status.APPROVED and not is_league_admin_or_manager(request.user):
        messages.error(request, 'Your team must be approved before you can customize kits.')
        return redirect('teams:team_dashboard', team_id=team.id)
    return _kit_editor(request, team, reverse('teams:team_dashboard', args=[team.id]))
