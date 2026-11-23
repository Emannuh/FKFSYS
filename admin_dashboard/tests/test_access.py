"""Access-control matrix for every admin_dashboard URL."""
from django.test import TestCase
from django.urls import reverse

from .factories import (
    ensure_groups, make_match, make_player, make_referee, make_report, make_superuser,
    make_team, make_user, make_zone,
)

LEAGUE_ADMIN_GET = ['approve_registrations', 'approve_reports', 'view_suspensions', 'statistics_dashboard',
                    'assign_zones', 'manage_transfers']
STAFF_GET = ['activity_logs', 'generate_fixtures_admin', 'reschedule_fixtures_admin']
SUPERUSER_GET = ['manage_league_admins']
POST_ONLY = ['toggle_registration', 'update_deadlines', 'create_league_admin']
POST_ONLY_USER = ['toggle_league_admin_status', 'reset_league_admin_password', 'delete_user']


class AccessMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.superuser = make_superuser()
        cls.league_admin = make_user('League Admin')
        cls.staff = make_user(is_staff=True)
        cls.team_manager = make_user('Team Managers')
        cls.referee_user = make_user('Referee')
        cls.target = make_user()
        team = make_team()
        cls.player = make_player(team)

    def url(self, name, *args):
        return reverse(f'admin_dashboard:{name}', args=args)

    def assert_login_redirect(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_anonymous_redirected_to_login(self):
        names = LEAGUE_ADMIN_GET + STAFF_GET + SUPERUSER_GET
        for name in names:
            with self.subTest(name=name):
                self.assert_login_redirect(self.client.get(self.url(name)))
        for name in ['manage_suspension', 'edit_user_roles', 'activity_log_detail', 'view_report']:
            with self.subTest(name=name):
                self.assert_login_redirect(self.client.get(self.url(name, 1)))

    def test_league_admin_pages(self):
        for user, expected in [(self.team_manager, 403), (self.referee_user, 403),
                               (self.league_admin, 200), (self.staff, 200), (self.superuser, 200)]:
            self.client.force_login(user)
            for name in LEAGUE_ADMIN_GET:
                with self.subTest(user=user.username, name=name):
                    self.assertEqual(self.client.get(self.url(name)).status_code, expected)
            with self.subTest(user=user.username, name='manage_suspension'):
                resp = self.client.get(self.url('manage_suspension', self.player.id))
                self.assertEqual(resp.status_code, expected)

    def test_staff_pages(self):
        for user, expected in [(self.league_admin, 403), (self.team_manager, 403),
                               (self.staff, 200), (self.superuser, 200)]:
            self.client.force_login(user)
            for name in STAFF_GET:
                with self.subTest(user=user.username, name=name):
                    self.assertEqual(self.client.get(self.url(name)).status_code, expected)

    def test_superuser_pages(self):
        for user, expected in [(self.league_admin, 403), (self.staff, 403), (self.superuser, 200)]:
            self.client.force_login(user)
            with self.subTest(user=user.username):
                self.assertEqual(self.client.get(self.url('manage_league_admins')).status_code, expected)
                self.assertEqual(self.client.get(self.url('edit_user_roles', self.target.id)).status_code, expected)

    def test_state_changing_endpoints_reject_get(self):
        self.client.force_login(self.superuser)
        for name in POST_ONLY:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(self.url(name)).status_code, 405)
        for name in POST_ONLY_USER:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(self.url(name, self.target.id)).status_code, 405)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)  # regression: GET used to toggle/reset/delete

    def test_privilege_endpoints_forbidden_for_league_admin_post(self):
        self.client.force_login(self.league_admin)
        for name in POST_ONLY_USER:
            with self.subTest(name=name):
                self.assertEqual(self.client.post(self.url(name, self.target.id)).status_code, 403)
        resp = self.client.post(self.url('edit_user_roles', self.league_admin.id), {'groups': ['League Admin']})
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(type(self.target).objects.filter(pk=self.target.pk).exists())

    def test_override_transfer_access(self):
        self.client.force_login(self.team_manager)
        self.assertEqual(self.client.get(self.url('override_transfer', 999)).status_code, 403)
        self.client.force_login(self.league_admin)
        self.assertEqual(self.client.get(self.url('override_transfer', 999)).status_code, 404)


class ViewReportObjectAccessTests(TestCase):
    """Regression: the denied branch reversed a non-existent URL (NoReverseMatch)."""

    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        zone = make_zone()
        match = make_match(make_team(zone=zone), make_team(zone=zone), zone)
        cls.author = make_user('Referee')
        cls.other_referee = make_user('Referee')
        cls.report = make_report(match, make_referee(cls.author))
        make_referee(cls.other_referee)
        cls.league_admin = make_user('League Admin')

    def get(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('admin_dashboard:view_report', args=[self.report.id]))

    def test_author_and_admin_can_view(self):
        self.assertEqual(self.get(self.league_admin).status_code, 200)
        self.assertNotEqual(self.get(self.author).status_code, 403)

    def test_other_referee_forbidden(self):
        self.assertEqual(self.get(self.other_referee).status_code, 403)
