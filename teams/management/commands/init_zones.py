from django.core.management.base import BaseCommand
from teams.models import Zone

class Command(BaseCommand):
    help = 'Initialize the three zones for FKF Meru League'
    
    def handle(self, *args, **kwargs):
        zones = [
            {'name': 'Zone A', 'description': 'Northern Zone'},
            {'name': 'Zone B', 'description': 'Central Zone'},
            {'name': 'Zone C', 'description': 'Southern Zone'},
        ]
        
        for zone_data in zones:
            zone, created = Zone.objects.get_or_create(
                name=zone_data['name'],
                defaults={'description': zone_data['description']}
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created zone: {zone.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Zone already exists: {zone.name}'))