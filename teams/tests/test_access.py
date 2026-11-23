"""URL-level access control for every teams URL, including IDOR regressions."""
from django.test import TestCase
from django.urls import reverse

from .factories import (
    make_manager_with_team, make_official, make_player, make_transfer, make_user, open_windows,
)

LOGIN = reverse('login')


class AccessControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager, cls.team = make_manager_with_team()
        cls.other_manager, cls.other_team = make_manager_with_team()
        cls.player = make_player(cls.team, jersey=7)
        cls.other_player = make_player(cls.other_team, jersey=9)
        cls.official = make_official(cls.team)
        cls.other_official = make_official(cls.other_team)
        cls.transfer = make_transfer(cls.other_player, cls.team, cls.manager)
        cls.league_admin = make_user('League Admin')
        cls.league_manager = make_user('League Manager')
        cls.referee = make_user('Referee')
        cls.ref_manager = make_user('Referees Manager')
        cls.superuser = make_user(superuser=True)

    def setUp(self):
        open_windows()

    def as_(self, user):
        self.client.force_login(user)

    # ── anonymous ────────────────────────────────────────────────────────
    def test_anonymous_redirected_to_login_everywhere_except_registration(self):
        t, p, o, tr = self.team.pk, self.player.pk, self.official.pk, self.transfer.pk
        protected = [
            ('teams:select_kit_colors', []), ('teams:team_officials', []),
            ('teams:delete_official', [o]), ('teams:team_manager_dashboard', []),
            ('teams:view_approved_squad', [1]), ('teams:update_kits', [t]),
            ('teams:add_players_approved', []), ('teams:add_player_action', []),
            ('teams:search_players', []), ('teams:request_transfer', [p]),
            ('teams:my_transfer_requests', []), ('teams:approve_transfer', [tr]),
            ('teams:reject_transfer', [tr]), ('teams:cancel_transfer', [tr]),
            ('teams:team_detail', [t]), ('teams:team_dashboard', [t]),
            ('teams:all_teams', []), ('teams:dashboard', []), ('teams:edit_team_info', [t]),
            ('teams:admin_manage_players', []), ('teams:admin_edit_player', [p]),
            ('teams:admin_delete_player', [p]), ('teams:admin_suspend_player', [p]),
            ('teams:admin_unsuspend_player', [p]), ('teams:admin_manage_officials', []),
            ('teams:admin_add_official', []), ('teams:admin_suspend_official', [o]),
            ('teams:admin_unsuspend_official', [o]), ('teams:admin_delete_team_official', [o]),
        ]
        for name, args in protected:
            with self.subTest(name=name):
                resp = self.client.get(reverse(name, args=args))
                self.assertEqual(resp.status_code, 302)
                self.assertTrue(resp['Location'].startswith(LOGIN), resp['Location'])

    def test_registration_is_public(self):
        self.assertEqual(self.client.get(reverse('teams:team_registration')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('teams:registration_success')),
                             reverse('teams:team_registration'))

    # ── regression: anonymous / any user could open any team dashboard ───
    def test_team_dashboard_object_level(self):
        url = reverse('teams:team_dashboard', args=[self.team.pk])
        for user, expected in [
            (self.manager, 200), (self.other_manager, 403), (self.referee, 403),
            (self.league_admin, 200), (self.league_manager, 200), (self.ref_manager, 200),
            (self.superuser, 200),
        ]:
            with self.subTest(user=user.username):
                self.as_(user)
                self.assertEqual(self.client.get(url).status_code, expected)

    def test_team_detail_object_level(self):
        url = reverse('teams:team_detail', args=[self.team.pk])
        for user, expected in [(self.manager, 200), (self.other_manager, 403), (self.referee, 403),
                               (self.league_admin, 200)]:
            with self.subTest(user=user.username):
                self.as_(user)
                self.assertEqual(self.client.get(url).status_code, expected)

    def test_league_admin_dashboard_requires_league_staff(self):
        url = reverse('teams:dashboard')
        for user, expected in [(self.manager, 403), (self.referee, 403), (self.ref_manager, 403),
                               (self.league_admin, 200), (self.league_manager, 200), (self.superuser, 200)]:
            with self.subTest(user=user.username):
                self.as_(user)
                self.assertEqual(self.client.get(url).status_code, expected)

    def test_update_kits_object_level(self):
        self.as_(self.other_manager)
        self.assertEqual(self.client.get(reverse('teams:update_kits', args=[self.team.pk])).status_code, 403)
        self.as_(self.manager)
        self.assertEqual(self.client.get(reverse('teams:update_kits', args=[self.team.pk])).status_code, 200)
        self.as_(self.league_manager)
        self.assertEqual(self.client.get(reverse('teams:update_kits', args=[self.team.pk])).status_code, 200)

    def test_league_staff_pages(self):
        p, o, t = self.player.pk, self.official.pk, self.team.pk
        pages = [
            ('teams:all_teams', []), ('teams:edit_team_info', [t]),
            ('teams:admin_manage_players', []), ('teams:admin_edit_player', [p]),
            ('teams:admin_delete_player', [p]), ('teams:admin_suspend_player', [p]),
            ('teams:admin_unsuspend_player', [p]), ('teams:admin_manage_officials', []),
            ('teams:admin_add_official', []), ('teams:admin_suspend_official', [o]),
            ('teams:admin_unsuspend_official', [o]), ('teams:admin_delete_team_official', [o]),
        ]
        for name, args in pages:
            url = reverse(name, args=args)
            with self.subTest(name=name, role='team manager'):
                self.as_(self.manager)
                self.assertEqual(self.client.get(url).status_code, 403)
            with self.subTest(name=name, role='referee'):
                self.as_(self.referee)
                self.assertEqual(self.client.get(url).status_code, 403)
            for staff in (self.league_admin, self.league_manager, self.superuser):
                with self.subTest(name=name, role=staff.username):
                    self.as_(staff)
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_manager_pages_render_for_own_team(self):
        self.as_(self.manager)
        for name in ('teams:select_kit_colors', 'teams:team_officials', 'teams:team_manager_dashboard',
                     'teams:add_players_approved', 'teams:search_players', 'teams:my_transfer_requests'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_users_without_team_are_redirected(self):
        self.as_(self.referee)
        for name in ('teams:select_kit_colors', 'teams:team_officials', 'teams:team_manager_dashboard',
                     'teams:add_players_approved', 'teams:search_players', 'teams:my_transfer_requests'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_state_changing_endpoints_reject_get(self):
        self.as_(self.manager)
        for name, args in [
            ('teams:delete_official', [self.official.pk]),
            ('teams:add_player_action', []),
            ('teams:request_transfer', [self.other_player.pk]),
            ('teams:approve_transfer', [self.transfer.pk]),
            ('teams:cancel_transfer', [self.transfer.pk]),
        ]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 405)
        self.official.refresh_from_db()  # still exists
        self.transfer.refresh_from_db()
        self.assertEqual(self.transfer.status, 'pending_parent')

    def test_admin_get_pages_do_not_mutate(self):
        self.as_(self.league_admin)
        self.client.get(reverse('teams:admin_delete_player', args=[self.player.pk]))
        self.client.get(reverse('teams:admin_suspend_player', args=[self.player.pk]))
        self.player.refresh_from_db()
        self.assertFalse(self.player.is_suspended)

    def test_delete_other_teams_official_is_404(self):
        self.as_(self.manager)
        resp = self.client.post(reverse('teams:delete_official', args=[self.other_official.pk]))
        self.assertEqual(resp.status_code, 404)
        self.other_official.refresh_from_db()

    def test_delete_own_official(self):
        self.as_(self.manager)
        resp = self.client.post(reverse('teams:delete_official', args=[self.official.pk]))
        self.assertRedirects(resp, reverse('teams:team_officials'))
        self.assertFalse(type(self.official).objects.filter(pk=self.official.pk).exists())
