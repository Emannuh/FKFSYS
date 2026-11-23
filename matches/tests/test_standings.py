from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from matches import services
from matches.models import LeagueTable, Match

from .helpers import make_match, make_team, make_zone


def row(team, zone):
    return LeagueTable.objects.get(team=team, zone=zone)


class StandingsTests(TestCase):
    def setUp(self):
        self.zone = make_zone()
        self.a = make_team(zone=self.zone)
        self.b = make_team(zone=self.zone)
        self.c = make_team(zone=self.zone)

    def complete(self, home, away, hs, as_, days_ago=1):
        return make_match(home, away, status=Match.Status.COMPLETED, home_score=hs, away_score=as_,
                          when=timezone.now() - timedelta(days=days_ago))

    def test_points_goal_difference_and_form(self):
        self.complete(self.a, self.b, 3, 1, days_ago=3)   # A win
        self.complete(self.c, self.a, 2, 2, days_ago=2)   # draw
        self.complete(self.a, self.c, 0, 1, days_ago=1)   # A loss (most recent)
        r = row(self.a, self.zone)
        self.assertEqual((r.matches_played, r.wins, r.draws, r.losses), (3, 1, 1, 1))
        self.assertEqual((r.goals_for, r.goals_against, r.goal_difference), (5, 4, 1))
        self.assertEqual(r.points, 4)
        self.assertEqual(r.form, 'LDW')  # most recent first
        b = row(self.b, self.zone)
        self.assertEqual((b.points, b.goal_difference, b.losses), (0, -2, 1))

    def test_form_limited_to_five(self):
        for i in range(7):
            self.complete(self.a, self.b, 1, 0, days_ago=10 - i)
        self.assertEqual(row(self.a, self.zone).form, 'WWWWW')
        self.assertEqual(row(self.a, self.zone).matches_played, 7)

    def test_resaving_result_does_not_double_count(self):
        m = self.complete(self.a, self.b, 2, 0)
        m.save()
        m.save()
        self.assertEqual(row(self.a, self.zone).matches_played, 1)
        self.assertEqual(row(self.a, self.zone).points, 3)

    def test_score_correction_recalculates(self):
        m = self.complete(self.a, self.b, 2, 0)
        m.home_score, m.away_score = 0, 1
        m.save()
        self.assertEqual(row(self.a, self.zone).points, 0)
        self.assertEqual(row(self.b, self.zone).points, 3)

    def test_uncompleting_and_deleting_remove_the_result(self):
        m = self.complete(self.a, self.b, 2, 0)
        m.status = Match.Status.POSTPONED
        m.save()
        self.assertEqual(row(self.a, self.zone).matches_played, 0)
        m.status = Match.Status.COMPLETED
        m.save()
        m.delete()
        self.assertEqual(row(self.a, self.zone).matches_played, 0)

    def test_changing_teams_refreshes_old_team(self):
        m = self.complete(self.a, self.b, 2, 0)
        m.away_team = self.c
        m.save()
        self.assertEqual(row(self.b, self.zone).matches_played, 0)
        self.assertEqual(row(self.c, self.zone).matches_played, 1)

    def test_scheduled_matches_ignored(self):
        make_match(self.a, self.b, home_score=5, away_score=0)
        self.assertEqual(row(self.a, self.zone).matches_played, 0)

    def test_leaguetable_save_always_derives_points(self):
        r = row(self.a, self.zone)
        r.wins, r.draws, r.points, r.goals_for, r.goal_difference = 2, 1, 99, 3, 50
        r.save()
        r.refresh_from_db()
        self.assertEqual((r.points, r.goal_difference), (7, 3))

    def test_move_match_to_round_swaps(self):
        m1 = make_match(self.a, self.b, round_number=1)
        m2 = make_match(self.c, self.a, round_number=2)
        swapped = services.move_match_to_round(m1, 2)
        self.assertEqual(swapped.pk, m2.pk)
        m1.refresh_from_db()
        m2.refresh_from_db()
        self.assertEqual((m1.round_number, m2.round_number), (2, 1))

    def test_recalculate_zone_rebuilds_tampered_rows(self):
        self.complete(self.a, self.b, 1, 0)
        LeagueTable.objects.filter(team=self.a).update(wins=10, points=30)
        services.recalculate_zone(self.zone.pk)
        self.assertEqual(row(self.a, self.zone).points, 3)
