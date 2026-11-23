from django.core.management.base import BaseCommand
from django.utils import timezone

from referees.models import MatchdaySquad


class Command(BaseCommand):
    help = 'Lock submitted/approved matchday squads whose match has kicked off.'

    def handle(self, *args, **options):
        now = timezone.now()
        candidates = MatchdaySquad.objects.filter(
            status__in=[MatchdaySquad.Status.SUBMITTED, MatchdaySquad.Status.APPROVED],
            match__match_date__date__lte=timezone.localdate(now),
        ).select_related('match', 'team')

        locked = 0
        for squad in candidates:
            if now >= squad.match.kickoff_datetime and squad.lock_squad():
                locked += 1
                self.stdout.write(f'Locked squad for {squad.team.team_name} ({squad.match})')
        self.stdout.write(self.style.SUCCESS(f'Successfully locked {locked} matchday squads'))
