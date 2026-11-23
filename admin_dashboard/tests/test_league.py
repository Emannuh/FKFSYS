"""League admin workflows and the /dashboard/ role router."""
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from matches.models import LeagueTable, Match, Suspension
from teams.models import LeagueSettings

from ..models import ActivityLog
from .factories import (
    User, ensure_groups, make_match, make_player, make_referee, make_report, make_superuser,
    make_team, make_user, make_zone,
)


class LeagueAdminTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.admin = make_user('League Admin')

    def setUp(self):
        self.client.force_login(self.admin)

    def url(self, name, *args):
        return reverse(f'admin_dashboard:{name}', args=args)


class ApproveRegistrationTests(LeagueAdminTestCase):
    def test_approve_creates_manager_without_default_password(self):
        team = make_team(team_name='Alpha FC', email='alpha@example.test')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('approve_registrations'), {'team_id': team.id, 'action': 'approve'})
        team.refresh_from_db()
        self.assertEqual(team.status, 'approved')
        manager = team.manager
        self.assertFalse(manager.has_usable_password())  # regression: was "<team_code>123"
        self.assertFalse(manager.check_password(f'{team.team_code.lower()}123'))
        self.assertTrue(manager.groups.filter(name='Team Managers').exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alpha@example.test'])
        self.assertTrue(ActivityLog.objects.filter(action='TEAM_APPROVE', object_id=team.pk).exists())

    def test_approve_links_existing_user_by_email(self):
        existing = make_user(email='beta@example.test')
        team = make_team(email='beta@example.test')
        self.client.post(self.url('approve_registrations'), {'team_id': team.id, 'action': 'approve'})
        team.refresh_from_db()
        self.assertEqual(team.manager, existing)
        self.assertTrue(existing.has_usable_password())

    def test_reject_and_only_pending_teams_actionable(self):
        team = make_team()
        self.client.post(self.url('approve_registrations'), {'team_id': team.id, 'action': 'reject'})
        team.refresh_from_db()
        self.assertEqual(team.status, 'rejected')
        resp = self.client.post(self.url('approve_registrations'), {'team_id': team.id, 'action': 'approve'})
        self.assertEqual(resp.status_code, 404)


class SuspensionTests(LeagueAdminTestCase):
    def setUp(self):
        super().setUp()
        self.player = make_player(make_team(status='approved'))

    def test_manage_page_renders(self):
        # regression: TemplateDoesNotExist admin_dashboard/manage_suspension.html
        resp = self.client.get(self.url('manage_suspension', self.player.id))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'admin_dashboard/manage_suspension.html')

    def test_suspend_then_clear(self):
        self.client.post(self.url('manage_suspension', self.player.id),
                         {'action': 'suspend', 'suspension_length': '3', 'reason': 'Violent conduct'})
        self.player.refresh_from_db()
        self.assertTrue(self.player.is_suspended)
        self.assertEqual(self.player.suspension_matches, 3)
        suspension = Suspension.objects.get(player=self.player)
        self.assertTrue(suspension.is_active)
        resp = self.client.get(self.url('view_suspensions'))
        self.assertContains(resp, self.player.full_name)

        self.client.post(self.url('manage_suspension', self.player.id), {'action': 'clear', 'reset_cards': 'yes'})
        self.player.refresh_from_db()
        suspension.refresh_from_db()
        self.assertFalse(self.player.is_suspended)
        self.assertFalse(suspension.is_active)
        self.assertEqual(
            list(ActivityLog.objects.exclude(action='LOGIN').order_by('id').values_list('action', flat=True)),
            ['SUSPENSION_CREATE', 'SUSPENSION_LIFT'],
        )

    def test_invalid_length_rejected(self):
        for value in ['abc', '0', '999']:
            self.client.post(self.url('manage_suspension', self.player.id),
                             {'action': 'suspend', 'suspension_length': value})
        self.assertFalse(Suspension.objects.exists())


class ZoneAndReportTests(LeagueAdminTestCase):
    def test_assign_zone_creates_table_row_and_logs(self):
        zone = make_zone()
        team = make_team(status='approved')
        self.client.post(self.url('assign_zones'), {'team_id': team.id, 'zone_id': zone.id})
        team.refresh_from_db()
        self.assertEqual(team.zone, zone)
        self.assertTrue(LeagueTable.objects.filter(team=team, zone=zone).exists())
        self.assertTrue(ActivityLog.objects.filter(action='ZONE_ASSIGN').exists())
        self.assertEqual(self.client.get(self.url('assign_zones')).status_code, 200)

    def test_assign_zone_requires_approved_team(self):
        zone = make_zone()
        team = make_team(status='pending')
        resp = self.client.post(self.url('assign_zones'), {'team_id': team.id, 'zone_id': zone.id})
        self.assertEqual(resp.status_code, 404)

    def test_reject_report_reopens_match(self):
        zone = make_zone()
        match = make_match(make_team(zone=zone), make_team(zone=zone), zone, status='completed')
        report = make_report(match, make_referee(make_user('Referee')), status='submitted')
        self.client.post(self.url('approve_reports'), {'report_id': report.id, 'action': 'reject'})
        report.refresh_from_db()
        match.refresh_from_db()
        self.assertEqual(report.status, 'rejected')
        self.assertEqual(match.status, 'scheduled')
        self.assertTrue(ActivityLog.objects.filter(action='MATCH_REPORT_REJECT').exists())


class RegistrationWindowTests(LeagueAdminTestCase):
    def test_toggle_flips_window_and_logs(self):
        before = LeagueSettings.get_settings().team_registration_open
        self.client.post(self.url('toggle_registration'), {'window_type': 'team'})
        self.assertNotEqual(LeagueSettings.get_settings().team_registration_open, before)
        self.assertTrue(ActivityLog.objects.filter(action='REGISTRATION_TOGGLE').exists())

    def test_update_deadlines(self):
        resp = self.client.post(self.url('update_deadlines'), {'team_deadline': '2099-01-01T10:00'})
        self.assertEqual(resp.status_code, 302)
        league_settings = LeagueSettings.get_settings()
        self.assertTrue(league_settings.team_registration_open)
        self.assertEqual(league_settings.team_registration_deadline.year, 2099)
        self.assertTrue(ActivityLog.objects.filter(action='CONFIG_CHANGE').exists())


class FixtureGenerationTests(TestCase):
    def setUp(self):
        self.client.force_login(make_superuser())

    def test_failed_regeneration_keeps_existing_fixtures(self):
        zone = make_zone(fixtures_generated=True)
        home, away = make_team(zone=zone, status='approved'), make_team(zone=zone, status='approved')
        make_match(home, away, zone)
        with mock.patch('admin_dashboard.views.fixtures.generate_fixtures_for_zone', return_value=(False, 'boom')):
            self.client.post(reverse('admin_dashboard:generate_fixtures_admin'),
                             {'zone_id': zone.id, 'regenerate': 'true'})
        zone.refresh_from_db()
        self.assertEqual(Match.objects.filter(zone=zone).count(), 1)
        self.assertTrue(zone.fixtures_generated)
        self.assertTrue(ActivityLog.objects.filter(action='FIXTURE_GENERATE', extra_data__success=False).exists())

    def test_needs_two_teams(self):
        zone = make_zone()
        make_team(zone=zone, status='approved')
        self.client.post(reverse('admin_dashboard:generate_fixtures_admin'), {'zone_id': zone.id})
        self.assertFalse(Match.objects.exists())


class DashboardRouterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_groups()

    def get(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('dashboard'))

    def test_no_role_user_gets_default_page(self):
        # regression: dashboard/default.html did not exist
        for user in [make_user(), make_user('referee'), make_user('league Admin')]:
            with self.subTest(user=user.username):
                resp = self.get(user)
                self.assertEqual(resp.status_code, 200)
                self.assertTemplateUsed(resp, 'dashboard/default.html')

    def test_team_manager_without_team_gets_default(self):
        resp = self.get(make_user('Team Managers'))
        self.assertTemplateUsed(resp, 'dashboard/default.html')

    def test_team_manager_with_pending_team(self):
        manager = make_user('Team Managers')
        make_team(manager=manager, status='pending')
        resp = self.get(manager)
        self.assertTemplateUsed(resp, 'dashboard/pending_approval.html')

    def test_league_admin_and_staff(self):
        for user in [make_user('League Admin'), make_user(is_staff=True)]:
            resp = self.get(user)
            self.assertTemplateUsed(resp, 'dashboard/league_manager.html')

    def test_referees_manager_and_referee(self):
        self.assertTemplateUsed(self.get(make_user('Referees Manager')), 'dashboard/referees_manager.html')
        resp = self.get(make_user('Referee'))
        self.assertEqual(resp.status_code, 302)

    def test_superuser_overview(self):
        resp = self.get(make_superuser())
        self.assertTemplateUsed(resp, 'admin_dashboard/dashboard.html')

    def test_anonymous(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(User.objects.filter(username='').exists())
