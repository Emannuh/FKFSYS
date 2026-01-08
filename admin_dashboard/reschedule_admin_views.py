
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from matches.models import Match

@staff_member_required
def reschedule_fixtures_admin(request):
    matches = Match.objects.filter(status__in=['scheduled', 'postponed']).order_by('match_date')
    return render(request, 'admin_dashboard/reschedule_fixtures.html', {'matches': matches})
