from django.core.management.base import BaseCommand
from django.utils import timezone
from teams.models import Team, Zone
from matches.models import Match
from datetime import timedelta
import random

class Command(BaseCommand):
    help = 'Generate automatic fixtures for teams in zones'
    
    def add_arguments(self, parser):
        parser.add_argument('--zone', type=str, help='Zone name to generate fixtures for')
        parser.add_argument('--start-date', type=str, help='Start date for fixtures (YYYY-MM-DD)')
        parser.add_argument('--interval', type=int, default=7, help='Days between matches')
    
    def handle(self, *args, **options):
        zone_name = options.get('zone')
        start_date = options.get('start_date')
        interval_days = options.get('interval')
        
        if zone_name:
            zones = Zone.objects.filter(name=zone_name)
        else:
            zones = Zone.objects.filter(is_active=True)
        
        if not zones.exists():
            self.stdout.write(self.style.ERROR('No zones found'))
            return
        
        for zone in zones:
            self.generate_zone_fixtures(zone, start_date, interval_days)
    
    def generate_zone_fixtures(self, zone, start_date_str, interval_days):
        teams = list(Team.objects.filter(
            zone=zone,
            status='approved',
            payment_status=True
        ))
        
        if len(teams) < 2:
            self.stdout.write(self.style.WARNING(f'Not enough teams in zone {zone.name}'))
            return
        
        self.stdout.write(f'Generating fixtures for zone: {zone.name}')
        self.stdout.write(f'Number of teams: {len(teams)}')
        
        if start_date_str:
            from datetime import datetime
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date() + timedelta(days=7)
        
        fixtures = self.round_robin(teams)
        
        match_count = 0
        round_number = 1
        
        for round_fixtures in fixtures:
            match_date = start_date + timedelta(days=(round_number - 1) * interval_days)
            
            for fixture in round_fixtures:
                if fixture[0] and fixture[1]:
                    home_team = fixture[0]
                    away_team = fixture[1]
                    
                    existing_match = Match.objects.filter(
                        home_team=home_team,
                        away_team=away_team,
                        zone=zone
                    ).exists()
                    
                    if not existing_match:
                        match = Match.objects.create(
                            home_team=home_team,
                            away_team=away_team,
                            zone=zone,
                            match_date=match_date,
                            kickoff_time='15:00:00',
                            venue=home_team.home_ground,
                            round=round_number
                        )
                        match_count += 1
                        self.stdout.write(f'Created: {home_team} vs {away_team} on {match_date}')
            
            round_number += 1
        
        zone.fixtures_generated = True
        zone.fixtures_generated_at = timezone.now()
        zone.save()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {match_count} matches for zone {zone.name}'))
    
    def round_robin(self, teams):
        if len(teams) % 2 == 1:
            teams.append(None)
        
        n = len(teams)
        fixtures = []
        
        for round_num in range(n - 1):
            round_fixtures = []
            
            for i in range(n // 2):
                home = teams[i]
                away = teams[n - 1 - i]
                
                if round_num % 2 == 1:
                    home, away = away, home
                
                if home and away:
                    round_fixtures.append((home, away))
            
            fixtures.append(round_fixtures)
            
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
        
        return fixtures 
    