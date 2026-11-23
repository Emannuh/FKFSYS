from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from teams.forms import AdminPlayerForm
from teams.models import Player

from .factories import adult_dob, make_manager_with_team, make_player, make_team, make_user, open_windows


def player_post(**overrides):
    data = {
        'first_name': 'Jane', 'last_name': 'Doe', 'date_of_birth': adult_dob().isoformat(),
        'id_number': '12345678', 'nationality': 'Kenyan', 'position': 'FW', 'jersey_number': '9',
    }
    data.update(overrides)
    return data


class AddPlayerTests(TestCase):
    def setUp(self):
        open_windows()
        self.manager, self.team = make_manager_with_team()
        self.client.force_login(self.manager)
        self.url = reverse('teams:add_player_action')

    def test_manager_adds_player_to_own_team(self):
        resp = self.client.post(self.url, player_post())
        self.assertRedirects(resp, reverse('teams:add_players_approved'))
        self.assertEqual(Player.objects.get().team, self.team)

    def test_manager_cannot_target_another_team(self):
        """IDOR regression: team_id in POST is ignored for non-staff."""
        other = make_team()
        self.client.post(self.url, player_post(team_id=other.pk))
        self.assertEqual(Player.objects.get().team, self.team)

    def test_validation_errors_rerender_without_saving(self):
        cases = {
            'too young': player_post(date_of_birth=adult_dob(10).isoformat()),
            'bad id': player_post(id_number='12'),
            'jersey range': player_post(jersey_number='150'),
        }
        for label, data in cases.items():
            with self.subTest(label):
                resp = self.client.post(self.url, data)
                self.assertEqual(resp.status_code, 400)
        self.assertFalse(Player.objects.exists())

    def test_duplicate_id_does_not_leak_other_players_identity(self):
        other_team = make_team()
        existing = make_player(other_team, id_number='12345678', first_name='Secret', last_name='Person')
        resp = self.client.post(self.url, player_post())
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, 'already registered', status_code=400)
        self.assertNotContains(resp, existing.last_name, status_code=400)
        self.assertNotContains(resp, other_team.team_name, status_code=400)

    def test_duplicate_jersey_rejected(self):
        make_player(self.team, jersey=9)
        resp = self.client.post(self.url, player_post())
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Player.objects.count(), 1)

    def test_new_captain_replaces_old(self):
        old = make_player(self.team, jersey=1, is_captain=True)
        self.client.post(self.url, player_post(is_captain='on'))
        old.refresh_from_db()
        self.assertFalse(old.is_captain)
        self.assertTrue(Player.objects.get(id_number='12345678').is_captain)

    def test_kit_must_be_set_first(self):
        self.team.kit_colors_set = False
        self.team.save()
        resp = self.client.post(self.url, player_post())
        self.assertRedirects(resp, reverse('teams:select_kit_colors'))

    def test_closed_window_blocks_managers_not_staff(self):
        open_windows(player_registration_open=False)
        resp = self.client.post(self.url, player_post())
        self.assertContains(resp, 'Player Registration Closed')
        self.assertFalse(Player.objects.exists())
        self.client.force_login(make_user('League Admin'))
        self.client.post(f'{self.url}?team_id={self.team.pk}', player_post())
        self.assertTrue(Player.objects.exists())

    def test_staff_without_team_sees_team_picker(self):
        self.client.force_login(make_user('League Manager'))
        resp = self.client.get(reverse('teams:add_players_approved'))
        self.assertTemplateUsed(resp, 'teams/admin_select_team_players.html')

    def test_oversized_photo_rejected(self):
        big = SimpleUploadedFile('p.png', b'\x89PNG' + b'0' * (5 * 1024 * 1024 + 10), content_type='image/png')
        resp = self.client.post(self.url, {**player_post(), 'photo': big})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Player.objects.exists())

    def test_verification_results_store_no_registry_identity(self):
        iprs = {'valid': True, 'verified': True, 'data': {'full_name': 'REGISTRY NAME'}, 'errors': []}
        with mock.patch('teams.forms.IPRSVerification.verify_id_number', return_value=iprs):
            self.client.post(self.url, player_post())
        player = Player.objects.get()
        self.assertTrue(player.iprs_verified)
        self.assertNotIn('REGISTRY NAME', str(player.verification_results))

    def test_iprs_mismatch_blocks_registration(self):
        iprs = {'valid': False, 'verified': True, 'data': None, 'errors': ['Name does not match']}
        with mock.patch('teams.forms.IPRSVerification.verify_id_number', return_value=iprs):
            resp = self.client.post(self.url, player_post())
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Player.objects.exists())


class AdminPlayerTests(TestCase):
    def setUp(self):
        self.team = make_team()
        self.player = make_player(self.team, jersey=5, id_number='11112222')

    def post_data(self, **overrides):
        data = {
            'first_name': self.player.first_name, 'last_name': self.player.last_name,
            'date_of_birth': '2000-01-01', 'nationality': 'Kenyan', 'id_number': self.player.id_number,
            'team': self.team.pk, 'position': 'MF', 'jersey_number': '5',
            'goals_scored': '4', 'yellow_cards': '0', 'red_cards': '0', 'matches_played': '3',
        }
        data.update(overrides)
        return data

    def test_league_manager_cannot_change_statistics(self):
        """goals_scored etc. are a League-Admin-only, audited correction."""
        self.client.force_login(make_user('League Manager'))
        url = reverse('teams:admin_edit_player', args=[self.player.pk])
        resp = self.client.post(url, self.post_data(first_name='Renamed'))
        self.assertRedirects(resp, reverse('teams:admin_manage_players'))
        self.player.refresh_from_db()
        self.assertEqual((self.player.first_name, self.player.goals_scored), ('Renamed', 0))

    def test_league_admin_can_correct_statistics_and_it_is_audited(self):
        self.client.force_login(make_user('League Admin'))
        url = reverse('teams:admin_edit_player', args=[self.player.pk])
        with self.assertLogs('teams.audit', level='INFO') as logs:
            self.client.post(url, self.post_data())
        self.player.refresh_from_db()
        self.assertEqual(self.player.goals_scored, 4)
        self.assertTrue(any('goals_scored corrected 0 -> 4' in line for line in logs.output))

    def test_negative_statistics_rejected(self):
        form = AdminPlayerForm(self.post_data(goals_scored='-1'), instance=self.player, can_edit_stats=True)
        self.assertFalse(form.is_valid())
        self.assertIn('goals_scored', form.errors)

    def test_suspend_and_unsuspend(self):
        self.client.force_login(make_user('League Admin'))
        self.client.post(reverse('teams:admin_suspend_player', args=[self.player.pk]),
                         {'suspension_matches': '2', 'suspension_reason': 'Red card'})
        self.player.refresh_from_db()
        self.assertEqual((self.player.is_suspended, self.player.suspension_matches), (True, 2))
        self.client.post(reverse('teams:admin_unsuspend_player', args=[self.player.pk]))
        self.player.refresh_from_db()
        self.assertEqual((self.player.is_suspended, self.player.suspension_matches), (False, 0))

    def test_suspend_requires_positive_matches(self):
        self.client.force_login(make_user('League Admin'))
        self.client.post(reverse('teams:admin_suspend_player', args=[self.player.pk]),
                         {'suspension_matches': '0', 'suspension_reason': 'x'})
        self.player.refresh_from_db()
        self.assertFalse(self.player.is_suspended)

    def test_delete_player(self):
        self.client.force_login(make_user('League Manager'))
        self.client.post(reverse('teams:admin_delete_player', args=[self.player.pk]))
        self.assertFalse(Player.objects.filter(pk=self.player.pk).exists())

    def test_search_filters(self):
        self.client.force_login(make_user('League Admin'))
        resp = self.client.get(reverse('teams:admin_manage_players'), {'search': 'zzz-no-match', 'team': 'abc'})
        self.assertEqual(list(resp.context['players']), [])
