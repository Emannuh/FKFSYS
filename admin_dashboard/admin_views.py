from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from teams.models import Zone, Team
from matches.models import Match
from matches.utils.fixture_generator import generate_fixtures_for_zone
from .activity_logger import log_activity, get_client_ip

@staff_member_required
def generate_fixtures_admin(request):
    # Get all zones (approved_teams_count is a property on the Zone model)
    zones = Zone.objects.all().order_by('name')
    
    if request.method == 'POST':
        zone_id = request.POST.get('zone_id')
        regenerate = request.POST.get('regenerate') == 'true'
        
        if zone_id:
            try:
                zone = Zone.objects.get(id=zone_id)
                
                # Check if regenerating existing fixtures
                if zone.fixtures_generated and not regenerate:
                    messages.warning(
                        request, 
                        f'Fixtures for {zone.name} have already been generated. Use the Regenerate button if you want to create new fixtures.'
                    )
                else:
                    approved_teams = Team.objects.filter(zone=zone, status='approved').count()
                    if approved_teams < 2:
                        messages.error(
                            request, 
                            f'Cannot generate fixtures for {zone.name}. At least 2 approved teams are required (currently has {approved_teams}).'
                        )
                    else:
                        # If regenerating, delete existing fixtures
                        if regenerate and zone.fixtures_generated:
                            existing_matches = Match.objects.filter(zone=zone)
                            
                            # Check if any matches have been played
                            played_matches = existing_matches.filter(status__in=['completed', 'ongoing']).count()
                            if played_matches > 0:
                                messages.error(
                                    request,
                                    f'Cannot regenerate fixtures for {zone.name}. {played_matches} match(es) have already been played or are ongoing. Delete or complete these matches first.'
                                )
                                # Log the failed attempt
                                log_activity(
                                    user=request.user,
                                    action='FIXTURE_REGENERATE',
                                    description=f'Failed attempt to regenerate fixtures for {zone.name} - {played_matches} matches already played',
                                    obj=zone,
                                    ip_address=get_client_ip(request),
                                    extra_data={'zone_id': zone.id, 'played_matches': played_matches}
                                )
                                return redirect('admin_dashboard:generate_fixtures_admin')
                            
                            # Delete existing fixtures and reset zone status
                            deleted_count = existing_matches.count()
                            existing_matches.delete()
                            zone.fixtures_generated = False
                            zone.fixture_generation_date = None
                            zone.save()
                            messages.info(request, f'Deleted {deleted_count} existing fixtures for {zone.name}.')
                            
                            # Log fixture deletion
                            log_activity(
                                user=request.user,
                                action='FIXTURE_DELETE',
                                description=f'Deleted {deleted_count} fixtures for {zone.name} before regeneration',
                                obj=zone,
                                ip_address=get_client_ip(request),
                                extra_data={'zone_id': zone.id, 'deleted_count': deleted_count}
                            )
                        
                        # Generate fixtures
                        success, message = generate_fixtures_for_zone(zone_id)
                        if success:
                            # Count generated matches
                            match_count = Match.objects.filter(zone=zone).count()
                            action = 'Regenerated' if regenerate else 'Generated'
                            messages.success(
                                request, 
                                f'✓ Successfully {action.lower()} {match_count} fixtures for {zone.name}! {message}'
                            )
                            
                            # Log successful fixture generation
                            log_activity(
                                user=request.user,
                                action='FIXTURE_REGENERATE' if regenerate else 'FIXTURE_GENERATE',
                                description=f'{action} {match_count} fixtures for {zone.name}',
                                obj=zone,
                                ip_address=get_client_ip(request),
                                extra_data={
                                    'zone_id': zone.id,
                                    'match_count': match_count,
                                    'approved_teams': approved_teams,
                                    'regenerated': regenerate
                                }
                            )
                        else:
                            messages.error(request, f'Failed to generate fixtures: {message}')
                            
                            # Log failed fixture generation
                            log_activity(
                                user=request.user,
                                action='FIXTURE_GENERATE',
                                description=f'Failed to generate fixtures for {zone.name}: {message}',
                                obj=zone,
                                ip_address=get_client_ip(request),
                                extra_data={'zone_id': zone.id, 'error': message}
                            )
                            
            except Zone.DoesNotExist:
                messages.error(request, 'Zone not found.')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
                
        return redirect('admin_dashboard:generate_fixtures_admin')
    
    # Prepare context with additional info
    context = {
        'zones': zones,
        'total_zones': zones.count(),
        'zones_with_fixtures': zones.filter(fixtures_generated=True).count(),
        'zones_pending': zones.filter(fixtures_generated=False).count(),
    }
    
    return render(request, 'admin/generate_fixtures.html', context)
