"""Registration, kits, officials, league settings and admin-site smoke tests."""
from datetime import timedelta
from unittest import mock

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from teams.external_verification import IPRSVerification
from teams.models import LeagueSettings, Team, TeamOfficial

from .factories import make_manager_with_team, make_official, make_team, make_user, open_windows


class RegistrationTests(TestCase):
    def setUp(self):
        open_windows()

    def data(self, **overrides):
        d = {'team_name': 'New FC', 'location': 'Meru', 'home_ground': 'Pitch',
             'contact_person': 'Coach', 'email': 'new@example.test', 'phone_digits': '712345678'}
        d.update(overrides)
        return d

    def test_register_creates_pending_team_and_goes_to_payment(self):
        resp = self.client.post(reverse('teams:team_registration'), self.data())
        team = Team.objects.get()
        self.assertRedirects(resp, reverse('payments:payment_page', args=[team.pk]), fetch_redirect_response=False)
        self.assertEqual((team.status, team.phone_number), ('pending', '+254712345678'))
        self.assertTrue(team.team_code)

    def test_duplicate_name_rejected_case_insensitive(self):
        make_team(team_name='New FC')
        self.client.post(reverse('teams:team_registration'), self.data(team_name='new fc'))
        self.assertEqual(Team.objects.count(), 1)

    def test_error_messages_are_escaped(self):
        """XSS regression: messages were rendered with |safe and included the team name."""
        make_team(team_name='<b>x</b>')
        resp = self.client.post(reverse('teams:team_registration'), self.data(team_name='<b>x</b>'))
        self.assertNotContains(resp, '<b>x</b>')

    def test_closed_registration(self):
        open_windows(team_registration_open=False)
        resp = self.client.get(reverse('teams:team_registration'))
        self.assertContains(resp, 'Team Registration Closed')


class KitTests(TestCase):
    def setUp(self):
        self.manager, self.team = make_manager_with_team(kit=False)
        self.client.force_login(self.manager)

    def kit(self, **overrides):
        d = {}
        for kit, color in [('home', '#ff0000'), ('away', '#ffffff'), ('gk_home', '#00ff00'), ('gk_away', '#ffff00')]:
            for part in ('jersey', 'shorts', 'socks'):
                d[f'{kit}_{part}_color'] = color
        d.update(overrides)
        return d

    def test_save_kits_marks_complete(self):
        resp = self.client.post(reverse('teams:select_kit_colors'), self.kit())
        self.assertRedirects(resp, reverse('teams:team_officials'))
        self.team.refresh_from_db()
        self.assertTrue(self.team.kit_colors_set)
        self.assertEqual(self.team.home_jersey_color, '#ff0000')

    def test_rejects_non_hex_colour(self):
        """CSS-injection regression: arbitrary strings were stored and rendered in style=."""
        self.client.post(reverse('teams:select_kit_colors'), self.kit(home_jersey_color='red;background:url(x)'))
        self.team.refresh_from_db()
        self.assertFalse(self.team.kit_colors_set)
        self.assertNotIn('url', self.team.home_jersey_color)

    def test_home_and_away_must_differ(self):
        self.client.post(reverse('teams:select_kit_colors'), self.kit(
            away_jersey_color='#ff0000', away_shorts_color='#ff0000'))
        self.team.refresh_from_db()
        self.assertFalse(self.team.kit_colors_set)

    def test_admin_update_kits_saves_target_team(self):
        """Regression: update_kits posted to select-kit, which edited the *user's* team."""
        self.client.force_login(make_user('League Manager'))
        resp = self.client.post(reverse('teams:update_kits', args=[self.team.pk]), self.kit())
        self.assertRedirects(resp, reverse('teams:team_dashboard', args=[self.team.pk]))
        self.team.refresh_from_db()
        self.assertTrue(self.team.kit_colors_set)


class OfficialTests(TestCase):
    def setUp(self):
        self.manager, self.team = make_manager_with_team()
        self.client.force_login(self.manager)

    def data(self, **overrides):
        d = {'action': 'add_official', 'position': 'head_coach', 'full_name': 'Coach A',
             'id_number': '22223333', 'phone_digits': '712345678', 'caf_license_number': 'CAF-1'}
        d.update(overrides)
        return d

    def test_add_official(self):
        self.client.post(reverse('teams:team_officials'), self.data())
        official = TeamOfficial.objects.get()
        self.assertEqual((official.team, official.phone_number), (self.team, '+254712345678'))

    def test_coach_requires_caf_licence(self):
        self.client.post(reverse('teams:team_officials'), self.data(caf_license_number=''))
        self.assertFalse(TeamOfficial.objects.exists())

    def test_one_official_per_position(self):
        make_official(self.team, position='head_coach')
        resp = self.client.post(reverse('teams:team_officials'), self.data())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TeamOfficial.objects.count(), 1)

    def test_progress_and_continue(self):
        for pos in TeamOfficial.Position:
            make_official(self.team, position=pos)
        resp = self.client.post(reverse('teams:team_officials'), {'action': 'continue'})
        self.assertRedirects(resp, reverse('teams:add_players_approved'))


class AdminOfficialTests(TestCase):
    def setUp(self):
        self.team = make_team()
        self.client.force_login(make_user('League Admin'))

    def test_admin_add_official(self):
        """Regression: duplicate view definitions read non-existent fields, so adding always failed."""
        resp = self.client.post(reverse('teams:admin_add_official'), {
            'team': self.team.pk, 'position': 'team_doctor', 'full_name': 'Dr X',
            'id_number': '33334444', 'phone_digits': '712345678',
        })
        self.assertRedirects(resp, reverse('teams:admin_manage_officials'))
        self.assertTrue(TeamOfficial.objects.filter(team=self.team, full_name='Dr X').exists())

    def test_suspend_uses_submitted_values(self):
        """Regression: the live (duplicate) view read 'matches'/'reason' instead of the template's fields."""
        official = make_official(self.team)
        self.client.post(reverse('teams:admin_suspend_official', args=[official.pk]),
                         {'suspension_matches': '3', 'suspension_reason': 'Misconduct'})
        official.refresh_from_db()
        self.assertEqual((official.is_suspended, official.suspension_matches, official.suspension_reason),
                         (True, 3, 'Misconduct'))

    def test_manage_officials_filters(self):
        make_official(self.team, is_suspended=True)
        resp = self.client.get(reverse('teams:admin_manage_officials'), {'status': 'suspended'})
        self.assertEqual(resp.context['suspended_officials'], 1)
        self.assertEqual(len(resp.context['officials']), 1)


class LeagueSettingsTests(TestCase):
    def test_manual_close_and_reopen_stamp_dates(self):
        league = open_windows()
        league.transfer_window_open = False
        league.save()
        league.refresh_from_db()
        self.assertIsNotNone(league.transfer_window_closed_date)
        league.transfer_window_open = True
        league.save()
        league.refresh_from_db()
        self.assertIsNone(league.transfer_window_closed_date)

    def test_deadline_auto_closes_with_deadline_as_closed_date(self):
        league = open_windows()
        deadline = timezone.now() - timedelta(hours=1)
        league.player_registration_deadline = deadline
        league.save()
        league = LeagueSettings.get_settings()
        self.assertFalse(league.player_registration_open)
        self.assertEqual(league.player_registration_closed_date, deadline)

    def test_singleton(self):
        LeagueSettings.get_settings()
        LeagueSettings().save()
        self.assertEqual(LeagueSettings.objects.count(), 1)


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class IPRSTests(TestCase):
    ENV = {'IPRS_ENABLED': 'true', 'IPRS_API_KEY': 'k', 'IPRS_API_SECRET': 's'}

    def setUp(self):
        cache.clear()

    def test_disabled_by_default(self):
        with mock.patch.dict('os.environ', {}, clear=True):
            result = IPRSVerification().verify_id_number('12345678')
        self.assertEqual((result['valid'], result['verified']), (True, False))

    def test_network_failure_degrades_and_logs_no_pii(self):
        with mock.patch.dict('os.environ', self.ENV), \
             mock.patch('teams.external_verification.requests.post', side_effect=requests.ConnectionError('boom 12345678')), \
             self.assertLogs('teams.external_verification', level='WARNING') as logs:
            result = IPRSVerification().verify_id_number('12345678', full_name='Jane Doe')
        self.assertEqual((result['valid'], result['verified']), (False, False))
        self.assertFalse(any('12345678' in line or 'Jane' in line for line in logs.output))

    def test_requests_use_timeout_and_mismatch_does_not_echo_registry(self):
        token = mock.Mock(status_code=200, json=lambda: {'access_token': 't', 'expires_in': 3600})
        lookup = mock.Mock(status_code=200, json=lambda: {
            'status': 'valid', 'full_name': 'Totally Different Person', 'date_of_birth': '1990-01-01'})
        with mock.patch.dict('os.environ', self.ENV), \
             mock.patch('teams.external_verification.requests.post', side_effect=[token, lookup]) as post:
            result = IPRSVerification().verify_id_number('12345678', full_name='Jane Doe', date_of_birth='2000-01-01')
        self.assertTrue(all(call.kwargs.get('timeout') for call in post.call_args_list))
        self.assertFalse(result['valid'])
        self.assertNotIn('Totally Different Person', ' '.join(result['errors']))
        self.assertNotIn('1990-01-01', ' '.join(result['errors']))


class AdminSiteTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user(superuser=True))
        make_team()

    def test_admin_pages_load(self):
        for url in ['/admin/teams/team/', '/admin/teams/team/import/', '/admin/teams/team/export/',
                    '/admin/teams/player/', '/admin/teams/player/import/', '/admin/teams/player/export/',
                    '/admin/teams/zone/', '/admin/teams/transferrequest/', '/admin/teams/teamofficial/',
                    '/admin/teams/leaguesettings/', '/admin/teams/transferhistory/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
