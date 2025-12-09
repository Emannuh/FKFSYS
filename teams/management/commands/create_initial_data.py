# teams/management/commands/create_initial_data.py
from django.core.management.base import BaseCommand
from teams.models import Zone, Team

class Command(BaseCommand):
    help = 'Creates initial data for the league system'
    
    def handle(self, *args, **kwargs):
        # Create Zones
        zones = [
            {'name': 'Zone A - South Meru'},
            {'name': 'Zone B - Central Meru'},
            {'name': 'Zone C - North Meru'},
        ]
        
        for zone_data in zones:
            zone, created = Zone.objects.get_or_create(name=zone_data['name'])
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created zone: {zone.name}'))
            else:
                self.stdout.write(f'Zone already exists: {zone.name}')
        
        # Create sample teams (optional)
        sample_teams = [
            {
                'team_name': 'Meru United FC',
                'location': 'Meru Town',
                'home_ground': 'Meru Stadium',
                'contact_person': 'John Kamau',
                'phone_number': '+254712345678',
                'email': 'meruunited@example.com',
                'status': 'approved',
                'payment_status': True,
            },
            {
                'team_name': 'Maua Warriors',
                'location': 'Maua',
                'home_ground': 'Maua Ground',
                'contact_person': 'Peter Mwangi',
                'phone_number': '+254723456789',
                'email': 'mauawarriors@example.com',
                'status': 'approved',
                'payment_status': True,
            },
        ]
        
        for team_data in sample_teams:
            team, created = Team.objects.get_or_create(
                team_name=team_data['team_name'],
                defaults=team_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created team: {team.team_name}'))
            else:
                self.stdout.write(f'Team already exists: {team.team_name}')
    
        self.stdout.write(self.style.SUCCESS('Initial data created successfully!'))