"""Team kit colours and images."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from fkf_league.permissions import is_league_admin_or_manager

from ..access import ensure_can_manage_team, get_managed_team
from ..forms import TeamKitForm
from ..models import Team


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
    return render(request, 'teams/select_kit.html', {'form': form, 'team': team})


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
