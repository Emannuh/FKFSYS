from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from matches.models import Match
from matches.utils.fixture_generator import update_match_date
from datetime import datetime

@staff_member_required
def reschedule_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        new_date = request.POST.get('new_date')
        new_kickoff_time = request.POST.get('new_kickoff_time')
        success, message = update_match_date(match.id, new_date, new_kickoff_time, new_kickoff_time)
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect(f'/matches/match/{match.id}/?updated=1')
    return render(request, 'admin_dashboard/reschedule_single.html', {'match': match})
