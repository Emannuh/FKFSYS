"""Business rules: pairing, fixture generation, standings, knockout progression."""
import itertools
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from ..models import TournamentGroupStanding, TournamentMatch
from ..services import (
    FixtureGenerationError,
    advance_knockout_winner,
    generate_fixtures,
    next_power_of_two,
    record_match_result,
    round_robin_rounds,
)
from . import factories as f


class RoundRobinPairingTests(SimpleTestCase):
    def check_schedule(self, n):
        teams = list(range(n))
        rounds = round_robin_rounds(teams)
        pairs = [frozenset(p) for r in rounds for p in r]
        self.assertEqual(len(pairs), n * (n - 1) // 2, 'every pair exactly once')
        self.assertEqual(set(pairs), {frozenset(c) for c in itertools.combinations(teams, 2)})
        self.assertEqual(len(rounds), n - 1 if n % 2 == 0 else n)
        for r in rounds:
            played = [t for p in r for t in p]
            self.assertEqual(len(played), len(set(played)), 'nobody plays twice in a round')

    def test_even_counts(self):
        for n in (2, 4, 6, 8):
            self.check_schedule(n)

    def test_odd_counts_give_one_bye_per_round(self):
        for n in (3, 5, 7):
            self.check_schedule(n)
            for r in round_robin_rounds(list(range(n))):
                self.assertEqual(len(r), (n - 1) // 2)

    def test_home_away_roughly_balanced(self):
        rounds = round_robin_rounds(list(range(6)))
        homes = [p[0] for r in rounds for p in r]
        for t in range(6):
            self.assertLessEqual(abs(homes.count(t) - 2.5), 1.5)

    def test_next_power_of_two(self):
        self.assertEqual([next_power_of_two(x) for x in (2, 3, 5, 8, 9)], [2, 4, 8, 8, 16])


class FixtureGenerationTests(TestCase):
    def setUp(self):
        self.first = timezone.now() + timedelta(days=3)

    def gen(self, tournament):
        return generate_fixtures(tournament, first_date=self.first, interval_days=7)

    def test_needs_two_teams(self):
        t = f.make_tournament()
        f.make_league_reg(t)
        f.make_league_reg(t, status='pending')
        with self.assertRaises(FixtureGenerationError):
            self.gen(t)

    def test_round_robin_creates_standings_table_and_all_pairs(self):
        t = f.make_tournament(format='round_robin')
        regs = [f.make_league_reg(t) for _ in range(5)]
        self.assertEqual(self.gen(t), 10)
        self.assertEqual(t.groups.count(), 1)
        self.assertEqual(TournamentGroupStanding.objects.filter(group__tournament=t).count(), 5)
        pairs = {frozenset((m.home_team_id, m.away_team_id)) for m in t.matches.all()}
        self.assertEqual(len(pairs), 10)
        self.assertTrue(all(m.group_id for m in t.matches.all()))
        self.assertEqual(len({r.pk for r in regs}), 5)

    def test_regeneration_is_idempotent(self):
        t = f.make_tournament(format='round_robin')
        for _ in range(4):
            f.make_league_reg(t)
        self.gen(t)
        self.gen(t)
        self.assertEqual(t.matches.count(), 6)
        self.assertEqual(t.groups.count(), 1)
        self.assertEqual(TournamentGroupStanding.objects.filter(group__tournament=t).count(), 4)

    def test_knockout_power_of_two(self):
        t = f.make_tournament(format='knockout')
        for _ in range(8):
            f.make_league_reg(t)
        self.gen(t)
        stages = list(t.matches.values_list('stage', flat=True))
        self.assertEqual(stages.count('quarter_final'), 4)
        self.assertEqual(stages.count('semi_final'), 2)
        self.assertEqual(stages.count('final'), 1)
        qf_teams = [x for m in t.matches.filter(stage='quarter_final') for x in (m.home_team_id, m.away_team_id)]
        self.assertEqual(len(set(qf_teams)), 8)

    def test_knockout_with_byes_keeps_every_team(self):
        """Regression: bye teams used to be dropped from the bracket entirely."""
        t = f.make_tournament(format='knockout')
        regs = [f.make_league_reg(t) for _ in range(5)]
        self.gen(t)
        placed = set()
        for m in t.matches.all():
            placed |= {m.home_team_id, m.away_team_id} - {None}
        self.assertEqual(placed, {r.pk for r in regs})
        self.assertEqual(t.matches.filter(stage='quarter_final').count(), 1)  # 5 -> 8: 3 byes
        self.assertEqual(t.matches.filter(stage='semi_final').count(), 2)

    def test_seeded_teams_get_byes(self):
        t = f.make_tournament(format='knockout')
        top = f.make_league_reg(t, seed=1)
        for _ in range(2):
            f.make_league_reg(t)
        self.gen(t)
        final = t.matches.get(stage='final')
        self.assertIn(top.pk, (final.home_team_id, final.away_team_id))
        self.assertFalse(t.matches.filter(stage='semi_final', home_team=top).exists())

    def test_group_knockout_clamps_group_count(self):
        """Regression: more groups than team pairs left empty groups."""
        t = f.make_tournament(format='group_knockout', group_count=4)
        for _ in range(5):
            f.make_league_reg(t)
        self.gen(t)
        self.assertEqual(t.groups.count(), 2)
        for g in t.groups.all():
            self.assertGreaterEqual(g.teams.count(), 2)
        self.assertEqual(t.matches.filter(stage='semi_final').count(), 2)
        self.assertEqual(t.matches.filter(stage='final').count(), 1)
        ko_start = t.matches.filter(stage='semi_final').order_by('match_date').first().match_date
        last_group = t.matches.filter(stage='group').order_by('-match_date').first().match_date
        self.assertGreater(ko_start, last_group)

    def test_oversized_knockout_rejected_and_rolled_back(self):
        t = f.make_tournament(format='knockout', max_teams=64)
        for _ in range(33):
            f.make_league_reg(t)
        with self.assertRaises(FixtureGenerationError):
            self.gen(t)
        self.assertEqual(t.matches.count(), 0)


class StandingsTests(TestCase):
    def setUp(self):
        self.t = f.make_tournament(format='round_robin')
        self.a, self.b, self.c = (f.make_league_reg(self.t) for _ in range(3))
        generate_fixtures(self.t, first_date=timezone.now(), interval_days=7)
        self.group = self.t.groups.get()

    def play(self, home, away, hs, as_):
        m = TournamentMatch.objects.get(
            tournament=self.t, home_team__in=[home, away], away_team__in=[home, away],
        )
        if m.home_team_id != home.pk:
            hs, as_ = as_, hs
        m.home_score, m.away_score = hs, as_
        record_match_result(m)
        return m

    def row(self, reg):
        return TournamentGroupStanding.objects.get(group=self.group, team_registration=reg)

    def test_points_and_goal_difference(self):
        self.play(self.a, self.b, 2, 0)
        self.play(self.b, self.c, 1, 1)
        a, b, c = self.row(self.a), self.row(self.b), self.row(self.c)
        self.assertEqual((a.played, a.won, a.points, a.goal_difference), (1, 1, 3, 2))
        self.assertEqual((b.played, b.drawn, b.lost, b.points, b.goal_difference), (2, 1, 1, 1, -2))
        self.assertEqual((c.played, c.points), (1, 1))

    def test_re_recording_result_does_not_double_count(self):
        m = self.play(self.a, self.b, 2, 0)
        record_match_result(m)
        m.home_score, m.away_score = (0, 1) if m.home_team_id == self.a.pk else (1, 0)
        record_match_result(m)
        a = self.row(self.a)
        self.assertEqual((a.played, a.won, a.lost, a.points), (1, 0, 1, 0))

    def test_ordering_uses_points_then_goal_difference(self):
        """Regression: table was ordered by wins, ignoring draws."""
        self.play(self.a, self.b, 1, 1)   # a 1pt, b 1pt
        self.play(self.a, self.c, 1, 1)   # a 2pts
        self.play(self.b, self.c, 3, 0)   # b 4pts (GD +3), c 1pt
        order = [s.team_registration_id for s in self.group.standings.all()]
        self.assertEqual(order, [self.b.pk, self.a.pk, self.c.pk])

    def test_goal_difference_breaks_points_tie(self):
        self.play(self.a, self.c, 5, 0)
        self.play(self.b, self.c, 1, 0)
        order = [s.team_registration_id for s in self.group.standings.all()]
        self.assertEqual(order[:2], [self.a.pk, self.b.pk])


class KnockoutProgressionTests(TestCase):
    def setUp(self):
        self.t = f.make_tournament(format='knockout')
        self.regs = [f.make_league_reg(self.t) for _ in range(4)]
        generate_fixtures(self.t, first_date=timezone.now(), interval_days=7)

    def test_winner_advances_to_correct_slot(self):
        sf1, sf2 = self.t.matches.filter(stage='semi_final').order_by('match_number')
        sf1.home_score, sf1.away_score = 2, 1
        record_match_result(sf1)
        sf2.home_score, sf2.away_score = 0, 3
        record_match_result(sf2)
        final = self.t.matches.get(stage='final')
        self.assertEqual(final.home_team_id, sf1.home_team_id)
        self.assertEqual(final.away_team_id, sf2.away_team_id)

    def test_penalties_decide_drawn_knockout(self):
        sf1 = self.t.matches.filter(stage='semi_final').order_by('match_number').first()
        sf1.home_score = sf1.away_score = 1
        sf1.home_penalties, sf1.away_penalties = 3, 4
        record_match_result(sf1)
        self.assertEqual(self.t.matches.get(stage='final').home_team_id, sf1.away_team_id)

    def test_final_has_no_next_round(self):
        final = self.t.matches.get(stage='final')
        final.home_team, final.away_team = self.regs[0], self.regs[1]
        final.status, final.home_score = 'completed', 1
        self.assertIsNone(advance_knockout_winner(final))
