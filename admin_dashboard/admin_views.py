from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from teams.models import Zone
from matches.utils.fixture_generator import generate_fixtures_for_zone

@staff_member_required
def generate_fixtures_admin(request):
    zones = Zone.objects.all()
    if request.method == 'POST':
        zone_id = request.POST.get('zone_id')
        if zone_id:
            success, message = generate_fixtures_for_zone(zone_id)
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
        return redirect('admin_dashboard:admin_dashboard')
    return render(request, 'admin/generate_fixtures.html', {'zones': zones})
