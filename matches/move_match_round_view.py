from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from matches.models import Match

@staff_member_required
def move_match_round(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        new_round = request.POST.get('new_round')
        try:
            old_round = match.round_number
            new_round = int(new_round)
            if old_round == new_round:
                messages.info(request, "No change in round.")
                return redirect('matches:manage_matches')
            # Check for another match in the same zone and new round
            swap_match = Match.objects.filter(zone=match.zone, round_number=new_round).exclude(id=match.id).first()
            if swap_match:
                swap_match.round_number = old_round
                swap_match.save()
            match.round_number = new_round
            match.save()
            if swap_match:
                messages.success(request, f"✅ Match moved to round {new_round} and swapped with match {swap_match.id}.")
            else:
                messages.success(request, f"✅ Match moved to round {new_round} successfully!")
            return redirect('matches:manage_matches')
        except Exception as e:
            messages.error(request, f"❌ Error moving match: {str(e)}")
            return redirect('matches:move_match_round', match_id=match_id)
    # GET request - show form
    rounds = Match.objects.values_list('round_number', flat=True).distinct().order_by('round_number')
    context = {
        'match': match,
        'rounds': rounds,
    }
    return render(request, 'admin_dashboard/move_match_round.html', context)
