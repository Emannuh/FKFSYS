from django.core.management.base import BaseCommand
from django.utils import timezone
from referees.models import MatchdaySquad, Match
from matches.models import Match as MatchModel


class Command(BaseCommand):
    help = 'Lock matchday squads that have reached kick-off time'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Find all approved squads for matches that have started
        started_matches = MatchModel.objects.filter(
            match_date__lte=now.date(),
            status='scheduled'
        )
        
        locked_count = 0
        for match in started_matches:
            if match.match_date == now.date():
                # Check if kick-off time has passed
                if match.kickoff_time:
                    # Handle kickoff_time as string or time object
                    kickoff_time = match.kickoff_time
                    if isinstance(kickoff_time, str):
                        from datetime import datetime
                        try:
                            kickoff_time = datetime.strptime(kickoff_time, '%H:%M:%S').time()
                        except (ValueError, AttributeError):
                            try:
                                kickoff_time = datetime.strptime(kickoff_time, '%H:%M').time()
                            except (ValueError, AttributeError):
                                continue
                    
                    match_datetime = timezone.make_aware(
                        timezone.datetime.combine(match.match_date, kickoff_time)
                    )
                    
                    if now >= match_datetime:
                        # Lock squads for this match
                        home_squad = MatchdaySquad.objects.filter(
                            match=match, 
                            team=match.home_team,
                            status='approved'
                        ).first()
                        
                        away_squad = MatchdaySquad.objects.filter(
                            match=match, 
                            team=match.away_team,
                            status='approved'
                        ).first()
                        
                        for squad in [home_squad, away_squad]:
                            if squad and not squad.is_locked():
                                squad.lock_squad()
                                locked_count += 1
                                self.stdout.write(
                                    f'Locked squad for {squad.team.team_name} vs {squad.match.away_team.team_name if squad.team == squad.match.home_team else squad.match.home_team.team_name}'
                                )
            else:
                # Match date has passed, lock all approved squads
                squads_to_lock = MatchdaySquad.objects.filter(
                    match=match,
                    status='approved'
                )
                
                for squad in squads_to_lock:
                    if not squad.is_locked():
                        squad.lock_squad()
                        locked_count += 1
                        self.stdout.write(
                            f'Locked squad for {squad.team.team_name} (match date passed)'
                        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully locked {locked_count} matchday squads')
        )