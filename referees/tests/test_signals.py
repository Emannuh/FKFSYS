"""Player tallies and league table stay correct and idempotent."""
from django.test import TestCase

from matches.models import LeagueTable
from referees import services
from referees.models import Caution, Expulsion, MatchGoal

from . import factories as f


class CleanSheetSignalTests(TestCase):
    def setUp(self):
        self.match = f.match()
        self.home_gk = f.player(self.match.home_team, 'GK')
        self.home_gk2 = f.player(self.match.home_team, 'GK')
        self.away_gk = f.player(self.match.away_team, 'GK')

    def sheets(self):
        return [p.clean_sheets for p in (self.home_gk, self.home_gk2, self.away_gk)
                if not p.refresh_from_db()]

    def test_unplayed_match_with_default_zero_scores_never_counts(self):
        # Regression: every save of a scheduled 0-0 match used to credit both teams' keepers.
        for _ in range(3):
            self.match.venue = 'Other'
            self.match.save()
        self.assertEqual(self.sheets(), [0, 0, 0])

    def test_completion_credits_once_and_resave_is_idempotent(self):
        self.match.home_score, self.match.away_score, self.match.status = 2, 0, 'completed'
        self.match.save()
        self.match.save()
        self.match.save()
        self.assertEqual(self.sheets(), [1, 1, 0])

    def test_score_correction_moves_or_removes_clean_sheet(self):
        self.match.home_score, self.match.away_score, self.match.status = 1, 0, 'completed'
        self.match.save()
        self.match.away_score = 1
        self.match.save()
        self.assertEqual(self.sheets(), [0, 0, 0])
        self.match.home_score = 0
        self.match.save()  # 0-1: away keeper keeps a clean sheet
        self.assertEqual(self.sheets(), [0, 0, 1])

    def test_goalless_draw_credits_both_and_uncompleting_reverses(self):
        self.match.status = 'completed'
        self.match.save()
        self.assertEqual(self.sheets(), [1, 1, 1])
        self.match.status = 'scheduled'
        self.match.save()
        self.assertEqual(self.sheets(), [0, 0, 0])

    def test_never_negative(self):
        self.match.status = 'completed'
        self.match.save()
        type(self.home_gk).objects.update(clean_sheets=0)  # manual reset by an admin
        self.match.status = 'postponed'
        self.match.save()
        self.assertEqual(self.sheets(), [0, 0, 0])


class GoalAndCardTallyTests(TestCase):
    def setUp(self):
        self.match = f.match()
        self.team = self.match.home_team
        self.p1 = f.player(self.team)
        self.p2 = f.player(self.team)

    def goal(self, player, **kw):
        return MatchGoal.objects.create(match=self.match, team=self.team, player=player, minute=10,
                                        jersey_number=player.jersey_number, **kw)

    def val(self, p, field):
        p.refresh_from_db()
        return getattr(p, field)

    def test_resaving_goal_does_not_double_count(self):
        g = self.goal(self.p1)
        g.save()
        g.minute = 12
        g.save()
        self.assertEqual(self.val(self.p1, 'goals_scored'), 1)

    def test_changing_scorer_moves_tally_and_delete_reverses(self):
        g = self.goal(self.p1)
        g.player = self.p2
        g.save()
        self.assertEqual((self.val(self.p1, 'goals_scored'), self.val(self.p2, 'goals_scored')), (0, 1))
        g.delete()
        self.assertEqual(self.val(self.p2, 'goals_scored'), 0)

    def test_own_goal_is_not_credited_and_type_change_is_tracked(self):
        g = self.goal(self.p1, goal_type=MatchGoal.GoalType.OWN_GOAL)
        self.assertEqual(self.val(self.p1, 'goals_scored'), 0)
        g.goal_type = MatchGoal.GoalType.NORMAL
        g.save()
        self.assertEqual(self.val(self.p1, 'goals_scored'), 1)

    def test_cards(self):
        c = Caution.objects.create(match=self.match, team=self.team, player=self.p1, minute=5, reason='x',
                                   jersey_number=1)
        c.save()
        e = Expulsion.objects.create(match=self.match, team=self.team, player=self.p1, minute=6, reason='x',
                                     jersey_number=1)
        self.assertEqual((self.val(self.p1, 'yellow_cards'), self.val(self.p1, 'red_cards')), (1, 1))
        c.player = self.p2
        c.save()
        self.assertEqual((self.val(self.p1, 'yellow_cards'), self.val(self.p2, 'yellow_cards')), (0, 1))
        c.delete()
        e.delete()
        self.assertEqual((self.val(self.p2, 'yellow_cards'), self.val(self.p1, 'red_cards')), (0, 0))


class RecordResultTests(TestCase):
    def test_marks_completed_via_save_and_never_touches_league_table_directly(self):
        match = f.match()
        gk = f.player(match.away_team, 'GK')
        services.record_result(match, 0, 0)
        services.record_result(match, 0, 0)  # resubmission
        match.refresh_from_db()
        gk.refresh_from_db()
        self.assertEqual((match.status, match.home_score, match.away_score), ('completed', 0, 0))
        self.assertEqual(gk.clean_sheets, 1)  # signals ran exactly once for the transition
        # Any league-table change comes from the matches app's own signals, not from referees code.
        self.assertFalse(
            LeagueTable.objects.filter(matches_played__gt=1).exists(),
            "resubmitting a result must not double-count",
        )
