"""Team officials managed by the team's own manager."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..access import get_managed_team
from ..forms import TeamOfficialForm
from ..models import TeamOfficial


@login_required
def team_officials(request):
    team = get_managed_team(request.user)
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')

    officials = TeamOfficial.objects.filter(team=team).order_by('position')
    filled = set(officials.values_list('position', flat=True))
    missing = [pos for pos in TeamOfficial.Position if pos not in filled]
    form = TeamOfficialForm(team=team)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_official':
            form = TeamOfficialForm(request.POST, request.FILES, team=team)
            if form.is_valid():
                official = form.save()
                messages.success(request, f"{official.get_position_display()} added successfully!")
                return redirect('teams:team_officials')
            for field, errors in form.errors.items():
                label = form.fields[field].label if field in form.fields else ''
                for error in errors:
                    messages.error(request, f"{label}: {error}" if label else error)
        elif action == 'continue':
            if missing:
                messages.warning(request, f"Please add: {', '.join(pos.label for pos in missing)}")
            else:
                messages.success(request, "All team officials registered! You can now add players.")
                return redirect('teams:add_players_approved')

    return render(request, 'teams/team_officials.html', {
        'team': team,
        'officials': officials,
        'form': form,
        'missing_positions': [pos.value for pos in missing],
        'filled_count': len(filled),
        'total_required': len(TeamOfficial.Position),
    })


@login_required
@require_POST
def delete_official(request, official_id):
    team = get_managed_team(request.user)
    official = get_object_or_404(TeamOfficial, pk=official_id, team=team) if team else None
    if official is None:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    name = official.full_name
    official.delete()
    messages.success(request, f"{name} removed.")
    return redirect('teams:team_officials')
