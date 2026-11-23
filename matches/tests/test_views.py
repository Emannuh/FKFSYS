from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from matches.models import LeagueTable, Match
from referees.models import MatchOfficials, Referee

from .helpers import make_match, make_team, make_user, make_zone


class Base(TestCase):
    def setUp(self):
        self.zone = make_zone()
        self.manager = make_user(groups=['Team Managers'])
        self.other_manager = make_user(groups=['Team Managers'])
        self.home = make_team(zone=self.zone, manager=self.manager)
        self.away = make_team(zone=self.zone)
        self.match = make_match(self.home, self.away)
        self.table = LeagueTable.objects.get(team=self.home, zone=self.zone)
        self.league_admin = make_user(groups=['League Admin'])
        self.staff = make_user(is_staff=True)
        self.referee_user = make_user(groups=['Referee'])


class PublicPagesTests(Base):
    def test_public_pages_ok_for_anonymous(self):
        urls = [
            reverse('matches:fixtures'),
            reverse('matches:fixtures') + '?status=all&zone=abc&round=x&date=bad',
            reverse('matches:league_tables'),
            reverse('matches:match_results'),
            reverse('matches:top_scorers'),
            reverse('matches:match_details', args=[self.match.pk]),
            # Regression: these two rendered templates that did not exist.
            reverse('matches:team_fixtures', args=[self.home.pk]),
            reverse('matches:zone_fixtures', args=[self.zone.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_team_fixtures_lists_team_matches_only(self):
        other = make_match(make_team(zone=self.zone), make_team(zone=self.zone))
        r = self.client.get(reverse('matches:team_fixtures', args=[self.home.pk]))
        self.assertIn(self.match, r.context['upcoming_matches'])
        self.assertNotIn(other, r.context['upcoming_matches'])

    def test_league_table_edit_link_only_for_league_admin(self):
        url = reverse('matches:admin_edit_league_table', args=[self.table.pk])
        self.assertNotContains(self.client.get(reverse('matches:league_tables')), url)
        self.client.force_login(self.league_admin)
        self.assertContains(self.client.get(reverse('matches:league_tables')), url)

    def test_match_details_shows_goals_section(self):
        r = self.client.get(reverse('matches:match_details', args=[self.match.pk]))
        self.assertContains(r, 'No goals recorded')
        self.assertNotContains(r, reverse('matches:admin_edit_match_result', args=[self.match.pk]))

    def test_removed_dead_routes(self):
        for name in ('league_manager_reschedule', 'start_match'):
            with self.assertRaises(NoReverseMatch):
                reverse(f'matches:{name}', args=[1])


class LeagueAdminViewsTests(Base):
    def test_edit_result_access(self):
        url = reverse('matches:admin_edit_match_result', args=[self.match.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.league_admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_edit_result_updates_standings(self):
        self.client.force_login(self.league_admin)
        url = reverse('matches:admin_edit_match_result', args=[self.match.pk])
        r = self.client.post(url, {'home_score': 2, 'away_score': 1})
        self.assertRedirects(r, reverse('matches:match_details', args=[self.match.pk]), fetch_redirect_response=False)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.COMPLETED)
        self.table.refresh_from_db()
        self.assertEqual((self.table.matches_played, self.table.points), (1, 3))

    def test_edit_result_rejects_negative(self):
        self.client.force_login(self.league_admin)
        url = reverse('matches:admin_edit_match_result', args=[self.match.pk])
        self.assertEqual(self.client.post(url, {'home_score': -1, 'away_score': 1}).status_code, 200)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.SCHEDULED)

    def test_edit_league_table(self):
        url = reverse('matches:admin_edit_league_table', args=[self.table.pk])
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(url, {}).status_code, 302)
        self.client.force_login(self.league_admin)
        data = dict(matches_played=2, wins=1, draws=1, losses=0, goals_for=3, goals_against=1)
        self.client.post(url, data)
        self.table.refresh_from_db()
        self.assertEqual((self.table.points, self.table.goal_difference), (4, 2))
        bad = dict(data, wins=5)  # W+D+L != P
        self.assertEqual(self.client.post(url, bad).status_code, 200)


class StaffViewsTests(Base):
    def test_staff_only(self):
        urls = [
            reverse('matches:manage_matches'),
            reverse('matches:create_match'),
            reverse('matches:edit_match', args=[self.match.pk]),
            reverse('matches:delete_match', args=[self.match.pk]),
            reverse('matches:move_match_round', args=[self.match.pk]),
            reverse('matches:reschedule_match', args=[self.match.pk]),
        ]
        for user in (None, self.manager, self.league_admin):
            if user:
                self.client.force_login(user)
            for url in urls:
                with self.subTest(user=user, url=url):
                    r = self.client.get(url)
                    self.assertEqual(r.status_code, 302)
                    self.assertIn('/admin/login/', r['Location'])
        self.client.force_login(self.staff)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_delete_requires_post(self):
        self.client.force_login(self.staff)
        url = reverse('matches:delete_match', args=[self.match.pk])
        self.client.get(url)
        self.assertTrue(Match.objects.filter(pk=self.match.pk).exists())
        self.client.post(url)
        self.assertFalse(Match.objects.filter(pk=self.match.pk).exists())

    def test_create_match_validation(self):
        self.client.force_login(self.staff)
        url = reverse('matches:create_match')
        base = {'home_team': self.home.pk, 'away_team': self.away.pk, 'zone': self.zone.pk,
                'match_date': '2026-12-06', 'kickoff_time': '15:00', 'venue': 'X', 'round_number': 2}
        for bad in ({'away_team': self.home.pk}, {'match_date': 'nope'}, {'kickoff_time': '3pm'},
                    {'status': 'hacked'}, {'zone': 9999}):
            self.client.post(url, {**base, **bad})
        self.assertEqual(Match.objects.count(), 1)
        self.client.post(url, base)
        created = Match.objects.exclude(pk=self.match.pk).get()
        self.assertEqual(created.kickoff_time, '15:00')

    def test_move_round_swaps(self):
        other = make_match(self.away, self.home, round_number=3)
        self.client.force_login(self.staff)
        self.client.post(reverse('matches:move_match_round', args=[self.match.pk]), {'new_round': 3})
        self.match.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual((self.match.round_number, other.round_number), (3, 1))

    def test_reschedule(self):
        self.client.force_login(self.staff)
        url = reverse('matches:reschedule_match', args=[self.match.pk])
        r = self.client.post(url, {'new_date': '2026-12-19', 'new_kickoff_time': '13:00', 'new_round': 1})
        self.assertEqual(r.status_code, 302)
        self.match.refresh_from_db()
        self.assertEqual(self.match.kickoff_time, '13:00')


class OfficialsViewTests(Base):
    def setUp(self):
        super().setUp()
        self.referee = Referee.objects.create(
            user=self.referee_user, first_name='Ref', last_name='One', fkf_number='FKF-1',
            email='ref@example.test', phone_number='+254700000001',
        )
        MatchOfficials(match=self.match, main_referee=self.referee).save(validate=False)
        self.url = reverse('matches:view_match_officials', args=[self.match.pk])

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_unrelated_team_manager_forbidden(self):
        # Regression: any logged-in user could read officials' phone numbers.
        self.client.force_login(self.other_manager)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_team_manager_sees_names_not_phones(self):
        self.client.force_login(self.manager)
        r = self.client.get(self.url)
        self.assertContains(r, 'Ref One')
        self.assertNotContains(r, '+254700000001')

    def test_appointed_referee_and_admin_see_phones(self):
        for user in (self.referee_user, self.league_admin):
            self.client.force_login(user)
            self.assertContains(self.client.get(self.url), '+254700000001')
