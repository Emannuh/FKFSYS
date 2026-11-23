"""League-staff team-official management (staff, League Admin, League Manager)."""
import logging

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from ..access import league_staff_required
from ..forms import AdminTeamOfficialForm
from ..models import Team, TeamOfficial

audit = logging.getLogger('teams.audit')


@league_staff_required
def admin_manage_officials(request):
    search_query = request.GET.get('search', '').strip()
    team_filter = request.GET.get('team', '')
    position_filter = request.GET.get('position', '')
    status_filter = request.GET.get('status', '')

    officials = TeamOfficial.objects.select_related('team')
    if search_query:
        officials = officials.filter(
            Q(full_name__icontains=search_query) | Q(phone_number__icontains=search_query)
        )
    if team_filter.isdigit():
        officials = officials.filter(team_id=int(team_filter))
    if position_filter:
        officials = officials.filter(position=position_filter)
    if status_filter == 'suspended':
        officials = officials.filter(is_suspended=True)
    elif status_filter == 'active':
        officials = officials.filter(is_suspended=False)

    totals = TeamOfficial.objects.aggregate(
        total_officials=Count('id'), suspended_officials=Count('id', filter=Q(is_suspended=True))
    )
    return render(request, 'teams/admin_manage_officials.html', {
        'officials': officials.order_by('team__team_name', 'position'),
        'teams': Team.objects.filter(status=Team.Status.APPROVED).order_by('team_name'),
        'search_query': search_query,
        'team_filter': team_filter,
        'position_filter': position_filter,
        'status_filter': status_filter,
        'position_choices': TeamOfficial.Position.choices,
        'active_officials': totals['total_officials'] - totals['suspended_officials'],
        **totals,
    })


@league_staff_required
def admin_add_team_official(request):
    form = AdminTeamOfficialForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            official = form.save()
            audit.info("official %s added to team %s by user %s", official.pk, official.team_id, request.user.pk)
            messages.success(request, f'Official {official.full_name} added to {official.team.team_name}')
            return redirect('teams:admin_manage_officials')
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'teams/admin_add_official.html', {'form': form})


@league_staff_required
def admin_suspend_official(request, official_id):
    official = get_object_or_404(TeamOfficial.objects.select_related('team'), pk=official_id)
    if request.method == 'POST':
        reason = request.POST.get('suspension_reason', '').strip()
        try:
            matches = int(request.POST.get('suspension_matches', ''))
        except ValueError:
            matches = 0
        if matches < 1 or not reason:
            messages.error(request, 'A positive number of matches and a reason are both required.')
            return redirect('teams:admin_suspend_official', official_id=official_id)
        official.is_suspended = True
        official.suspension_matches = matches
        official.suspension_reason = reason
        official.save(update_fields=['is_suspended', 'suspension_matches', 'suspension_reason'])
        audit.info("official %s suspended for %s matches by user %s", official.pk, matches, request.user.pk)
        messages.success(request, f'Official {official.full_name} suspended for {matches} match(es)')
        return redirect('teams:admin_manage_officials')
    return render(request, 'teams/admin_suspend_official.html', {'official': official})


@league_staff_required
def admin_unsuspend_official(request, official_id):
    official = get_object_or_404(TeamOfficial.objects.select_related('team'), pk=official_id)
    if request.method == 'POST':
        official.is_suspended = False
        official.suspension_matches = 0
        official.suspension_reason = ''
        official.suspension_end = None
        official.save(update_fields=['is_suspended', 'suspension_matches', 'suspension_reason', 'suspension_end'])
        audit.info("official %s unsuspended by user %s", official.pk, request.user.pk)
        messages.success(request, f'Official {official.full_name} suspension lifted')
        return redirect('teams:admin_manage_officials')
    return render(request, 'teams/admin_unsuspend_official.html', {'official': official})


@league_staff_required
def admin_delete_official(request, official_id):
    official = get_object_or_404(TeamOfficial.objects.select_related('team'), pk=official_id)
    if request.method == 'POST':
        name, team_name, pk = official.full_name, official.team.team_name, official.pk
        official.delete()
        audit.info("official %s deleted by user %s", pk, request.user.pk)
        messages.success(request, f'Official {name} removed from {team_name}')
        return redirect('teams:admin_manage_officials')
    return render(request, 'teams/admin_delete_official.html', {'official': official})
