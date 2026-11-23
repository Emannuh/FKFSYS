import random
from collections import defaultdict
from datetime import date, time

from django.test import TestCase
from django.utils import timezone

from matches.models import Match
from matches.utils.fixture_generator import (
    first_match_day,
    generate_fixtures_for_zone,
    regenerate_fixtures_for_zone,
    round_robin_pairings,
    update_match_date,
)

from .helpers import local_dt, make_match, make_team, make_zone


class RoundRobinTests(TestCase):
    def test_properties_for_even_and_odd_team_counts(self):
        for n in range(2, 15):
            with self.subTest(n=n):
                rounds = round_robin_pairings(list(range(n)))
                self.assertEqual(len(rounds), n - 1 if n % 2 == 0 else n)
                pairs = [frozenset(p) for rnd in rounds for p in rnd]
                self.assertEqual(len(pairs), n * (n - 1) // 2)
                self.assertEqual(len(set(pairs)), len(pairs), "every pair exactly once")
                venues = defaultdict(list)
                for rnd in rounds:
                    playing = [t for p in rnd for t in p]
                    self.assertEqual(len(playing), len(set(playing)), "no team twice in a round")
                    for home, away in rnd:
                        venues[home].append('H')
                        venues[away].append('A')
                for team, seq in venues.items():
                    diff = abs(seq.count('H') - seq.count('A'))
                    self.assertLessEqual(diff, 0 if n % 2 else 1, f"home/away balance team {team}")
                    streak = longest = 1
                    for a, b in zip(seq, seq[1:]):
                        streak = streak + 1 if a == b else 1
                        longest = max(longest, streak)
                    self.assertLessEqual(longest, 2, f"venue streak team {team}")

    def test_odd_count_every_team_has_one_bye(self):
        rounds = round_robin_pairings(list(range(5)))
        for team in range(5):
            sat_out = sum(1 for rnd in rounds if team not in {t for p in rnd for t in p})
            self.assertEqual(sat_out, 1)


class GenerateFixturesTests(TestCase):
    def setUp(self):
        self.zone = make_zone(match_day_of_week=6)
        self.teams = [make_team(zone=self.zone, status='pending') for _ in range(5)]
        for t in self.teams:  # approve without the auto-generation signal kicking in yet
            type(t).objects.filter(pk=t.pk).update(status='approved')

    def test_generates_single_round_robin_with_aware_dates_on_match_day(self):
        ok, _ = generate_fixtures_for_zone(self.zone.pk, rng=random.Random(1))
        self.assertTrue(ok)
        matches = Match.objects.filter(zone=self.zone)
        self.assertEqual(matches.count(), 10)
        self.assertEqual(matches.values('round_number').distinct().count(), 5)
        for m in matches:
            self.assertTrue(timezone.is_aware(m.match_date))
            local = timezone.localtime(m.match_date)
            self.assertEqual(local.weekday(), 6)
            self.assertEqual(local.strftime('%H:%M'), m.kickoff_time)
            self.assertEqual(m.venue, m.home_team.home_ground)
        self.zone.refresh_from_db()
        self.assertTrue(self.zone.fixtures_generated)

    def test_second_generation_refused(self):
        generate_fixtures_for_zone(self.zone.pk)
        ok, _ = generate_fixtures_for_zone(self.zone.pk)
        self.assertFalse(ok)
        self.assertEqual(Match.objects.filter(zone=self.zone).count(), 10)

    def test_needs_two_teams(self):
        empty = make_zone()
        self.assertFalse(generate_fixtures_for_zone(empty.pk)[0])
        self.assertFalse(generate_fixtures_for_zone(999999)[0])

    def test_regenerate_replaces_unplayed_fixtures(self):
        generate_fixtures_for_zone(self.zone.pk)
        ok, _ = regenerate_fixtures_for_zone(self.zone.pk)
        self.assertTrue(ok)
        self.assertEqual(Match.objects.filter(zone=self.zone).count(), 10)

    def test_regenerate_refuses_when_results_exist(self):
        # Regression: regeneration used to delete completed matches (and cascade reports/goals).
        generate_fixtures_for_zone(self.zone.pk)
        m = Match.objects.filter(zone=self.zone).first()
        m.status = Match.Status.COMPLETED
        m.save()
        ok, _ = regenerate_fixtures_for_zone(self.zone.pk)
        self.assertFalse(ok)
        self.assertTrue(Match.objects.filter(pk=m.pk).exists())

    def test_first_match_day_is_strictly_future(self):
        zone = make_zone(match_day_of_week=6)
        sunday = date(2026, 11, 22)  # a Sunday
        self.assertEqual(first_match_day(zone, today=sunday), date(2026, 11, 29))
        self.assertEqual(first_match_day(zone, today=date(2026, 11, 23)), date(2026, 11, 29))


class AutoGenerationSignalTests(TestCase):
    def test_fourth_approved_team_triggers_generation_once(self):
        zone = make_zone()
        for _ in range(3):
            make_team(zone=zone)
        self.assertFalse(Match.objects.filter(zone=zone).exists())
        with self.captureOnCommitCallbacks(execute=True):
            make_team(zone=zone)
        self.assertEqual(Match.objects.filter(zone=zone).count(), 6)
        with self.captureOnCommitCallbacks(execute=True):
            make_team(zone=zone)  # 5th team: fixtures already generated, nothing new
        self.assertEqual(Match.objects.filter(zone=zone).count(), 6)

    def test_approved_team_gets_league_table_row(self):
        zone = make_zone()
        team = make_team(zone=zone)
        self.assertTrue(team.league_table.filter(zone=zone).exists())


class RescheduleTests(TestCase):
    def test_keeps_local_kickoff_time_when_no_time_given(self):
        # Regression: used the UTC time of match_date and re-localised it (3h drift per reschedule).
        zone = make_zone()
        m = make_match(make_team(zone=zone), make_team(zone=zone), when=local_dt(2026, 12, 5, 15, 0))
        ok, _ = update_match_date(m.pk, '2026-12-12')
        self.assertTrue(ok)
        m.refresh_from_db()
        self.assertEqual(timezone.localtime(m.match_date).time(), time(15, 0))
        self.assertEqual(timezone.localtime(m.match_date).date(), date(2026, 12, 12))

    def test_with_time(self):
        zone = make_zone()
        m = make_match(make_team(zone=zone), make_team(zone=zone))
        ok, _ = update_match_date(m.pk, '2026-12-12', '17:30')
        m.refresh_from_db()
        self.assertEqual(m.kickoff_time, '17:30')
        self.assertEqual(timezone.localtime(m.match_date).time(), time(17, 30))

    def test_invalid_input(self):
        self.assertFalse(update_match_date(999999, '2026-12-12')[0])
        zone = make_zone()
        m = make_match(make_team(zone=zone), make_team(zone=zone))
        self.assertFalse(update_match_date(m.pk, 'not-a-date')[0])

    def test_kickoff_datetime_uses_local_date(self):
        # Regression: used the UTC date, so a midnight-EAT match showed the previous day.
        zone = make_zone()
        m = make_match(make_team(zone=zone), make_team(zone=zone), when=local_dt(2026, 12, 5, 0, 0),
                       kickoff_time='15:00')
        m.refresh_from_db()
        self.assertEqual(timezone.localtime(m.kickoff_datetime), local_dt(2026, 12, 5, 15, 0))
