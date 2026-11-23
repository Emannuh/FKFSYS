"""Access control, object-level authorisation, POST-only and view workflows."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import (
    ExternalTeam,
    Tournament,
    TournamentMatch,
    TournamentMatchdaySquad,
    TournamentMatchOfficials,
    TournamentPlayerRegistration,
    TournamentTeamRegistration,
)
from . import factories as f


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = f.make_user('League Admin')
        cls.staff = f.make_user(is_staff=True)
        cls.ref_manager = f.make_user('Referees Manager')
        cls.manager = f.make_user('Team Managers')
        cls.other_manager = f.make_user('Team Managers')
        cls.referee_user = f.make_user('Referee')
        cls.referee = f.make_referee(cls.referee_user)

        cls.t = f.make_tournament()
        cls.team = f.make_team(manager=cls.manager)
        cls.other_team = f.make_team(manager=cls.other_manager)
        cls.reg = f.make_league_reg(cls.t, cls.team)
        cls.other_reg = f.make_league_reg(cls.t, cls.other_team)
        cls.match = f.make_match(cls.t, cls.reg, cls.other_reg)

    def login(self, user):
        self.client.force_login(user)


class AccessMatrixTests(Base):
    """Every URL: anonymous, wrong role and right role."""

    def admin_urls(self):
        s, m = self.t.slug, self.match.pk
        return [
            reverse('tournaments:admin_dashboard'),
            reverse('tournaments:create_tournament'),
            reverse('tournaments:edit_tournament', args=[s]),
            reverse('tournaments:delete_tournament', args=[s]),
            reverse('tournaments:import_league_teams', args=[s]),
            reverse('tournaments:manage_registrations', args=[s]),
            reverse('tournaments:review_registration', args=[self.reg.pk]),
            reverse('tournaments:create_match', args=[s]),
            reverse('tournaments:record_result', args=[m]),
            reverse('tournaments:generate_fixtures', args=[s]),
            reverse('tournaments:edit_tournament_match', args=[m]),
        ]

    def officials_urls(self):
        return [
            reverse('tournaments:appoint_officials', args=[self.match.pk]),
            reverse('tournaments:matches_needing_officials', args=[self.t.slug]),
        ]

    def test_public_pages(self):
        for url in [reverse('tournaments:tournament_list'),
                    reverse('tournaments:tournament_detail', args=[self.t.slug]),
                    reverse('tournaments:tournament_fixtures', args=[self.t.slug]),
                    reverse('tournaments:tournament_standings', args=[self.t.slug])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_draft_hidden_from_public(self):
        draft = f.make_tournament(status=Tournament.Status.DRAFT)
        url = reverse('tournaments:tournament_detail', args=[draft.slug])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login(self.manager)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_pages(self):
        for url in self.admin_urls():
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302, url)
            for user in (self.manager, self.referee_user, self.ref_manager):
                self.login(user)
                self.assertEqual(self.client.get(url).status_code, 403, (url, user))
            for user in (self.admin, self.staff):
                self.login(user)
                self.assertEqual(self.client.get(url).status_code, 200, (url, user))

    def test_officials_pages_allow_referees_manager(self):
        for url in self.officials_urls():
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)
            for user in (self.manager, self.referee_user):
                self.login(user)
                self.assertEqual(self.client.get(url).status_code, 403, (url, user))
            for user in (self.admin, self.ref_manager):
                self.login(user)
                self.assertEqual(self.client.get(url).status_code, 200, (url, user))

    def test_officials_get_creates_nothing(self):
        self.login(self.admin)
        self.client.get(reverse('tournaments:appoint_officials', args=[self.match.pk]))
        self.assertFalse(TournamentMatchOfficials.objects.filter(match=self.match).exists())

    def test_login_required_pages(self):
        urls = [reverse('tournaments:tournament_team_matches'),
                reverse('tournaments:tournament_referee_squad_list'),
                reverse('tournaments:tournament_submit_squad', args=[self.match.pk]),
                reverse('tournaments:register_team', args=[self.t.slug]),
                reverse('tournaments:register_players', args=[self.t.slug])]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302)
            self.assertIn('/login', resp['Location'])

    def test_team_matches_url_not_shadowed_by_slug(self):
        """Regression: 'my-matches/' was matched as a tournament slug -> 404."""
        self.login(self.manager)
        resp = self.client.get(reverse('tournaments:tournament_team_matches'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['matches_data']), 1)

    def test_reserved_slug_not_generated(self):
        t = f.make_tournament(name='My Matches')
        self.assertNotEqual(t.slug, 'my-matches')

    def test_referee_squad_list(self):
        self.login(self.referee_user)
        self.assertEqual(self.client.get(reverse('tournaments:tournament_referee_squad_list')).status_code, 200)
        self.login(self.admin)  # no referee profile
        self.assertRedirects(self.client.get(reverse('tournaments:tournament_referee_squad_list')),
                             reverse('dashboard'), fetch_redirect_response=False)

    def test_admin_buttons_only_for_admins(self):
        url = reverse('tournaments:tournament_detail', args=[self.t.slug])
        edit = reverse('tournaments:edit_tournament', args=[self.t.slug])
        self.login(self.manager)  # group member but not an admin
        self.assertNotContains(self.client.get(url), edit)
        self.login(self.admin)
        self.assertContains(self.client.get(url), edit)


class PostOnlyTests(Base):
    def test_change_status_rejects_get(self):
        self.login(self.admin)
        url = reverse('tournaments:change_status', args=[self.t.slug])
        self.assertEqual(self.client.get(url, {'status': 'cancelled'}).status_code, 405)
        self.t.refresh_from_db()
        self.assertEqual(self.t.status, 'registration')
        self.client.post(url, {'status': 'ongoing'})
        self.t.refresh_from_db()
        self.assertEqual(self.t.status, 'ongoing')

    def test_change_status_requires_admin(self):
        self.login(self.manager)
        url = reverse('tournaments:change_status', args=[self.t.slug])
        self.assertEqual(self.client.post(url, {'status': 'cancelled'}).status_code, 403)

    def test_delete_requires_post(self):
        self.login(self.admin)
        t = f.make_tournament()
        url = reverse('tournaments:delete_tournament', args=[t.slug])
        self.client.get(url)
        self.assertTrue(Tournament.objects.filter(pk=t.pk).exists())
        self.client.post(url)
        self.assertFalse(Tournament.objects.filter(pk=t.pk).exists())

    def test_approve_squad_rejects_other_methods(self):
        squad = TournamentMatchdaySquad.objects.create(match=self.match, team_registration=self.reg)
        self.login(self.referee_user)
        resp = self.client.put(reverse('tournaments:tournament_approve_squad', args=[squad.pk]))
        self.assertEqual(resp.status_code, 405)


class ExternalRegistrationTests(TestCase):
    def setUp(self):
        self.t = f.make_tournament(allow_external_teams=True)
        self.url = reverse('tournaments:register_external_team', args=[self.t.slug])

    def data(self, **kw):
        d = dict(team_name='Visitors United', contact_person='Jane Doe', phone_number='+254711111111',
                 email='new.manager@example.test', manager_password='Very-strong-pass-77',
                 home_jersey_color='#ff0000', away_jersey_color='#ffffff')
        d.update(kw)
        return d

    def test_existing_email_cannot_take_over_account(self):
        """Security regression: an existing email used to be logged in without a password."""
        victim = f.make_user(is_staff=True)
        resp = self.client.post(self.url, self.data(email=victim.email))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ExternalTeam.objects.exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_password_required_and_validated(self):
        """Security regression: blank password used to create '<username>123'."""
        self.client.post(self.url, self.data(manager_password=''))
        self.client.post(self.url, self.data(manager_password='short'))
        self.assertFalse(User.objects.filter(email='new.manager@example.test').exists())

    def test_new_account_created_and_logged_in(self):
        resp = self.client.post(self.url, self.data())
        self.assertRedirects(resp, reverse('tournaments:tournament_detail', args=[self.t.slug]),
                             fetch_redirect_response=False)
        user = User.objects.get(email='new.manager@example.test')
        self.assertTrue(user.check_password('Very-strong-pass-77'))
        self.assertTrue(user.groups.filter(name='Team Managers').exists())
        self.assertFalse(user.is_staff)
        ext = ExternalTeam.objects.get()
        self.assertEqual(ext.manager_user, user)
        self.assertEqual(ext.tournament_registrations.get().status, 'pending')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_duplicate_team_name_is_a_form_error(self):
        """Regression: duplicate name raised IntegrityError (500)."""
        self.client.post(self.url, self.data())
        self.client.logout()
        resp = self.client.post(self.url, self.data(email='second@example.test', team_name='visitors united'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ExternalTeam.objects.count(), 1)

    def test_logged_in_user_links_own_account(self):
        user = f.make_user()
        self.client.force_login(user)
        self.client.post(self.url, self.data(email=''))
        self.assertEqual(ExternalTeam.objects.get().manager_user, user)

    def test_closed_registration(self):
        self.t.status = 'registration_closed'
        self.t.save()
        self.client.post(self.url, self.data())
        self.assertFalse(ExternalTeam.objects.exists())


class ExternalPlayersIDORTests(TestCase):
    def setUp(self):
        self.owner = f.make_user('Team Managers')
        self.intruder = f.make_user('Team Managers')
        self.t = f.make_tournament()
        self.reg = f.make_external_reg(self.t, manager=self.owner)
        self.url = reverse('tournaments:register_external_players',
                           args=[self.t.slug, self.reg.external_team.pk])
        self.payload = dict(first_name='A', last_name='B', position='GK', jersey_number=1)

    def test_other_user_forbidden(self):
        """Security regression: any logged-in user could add players to any external team."""
        self.client.force_login(self.intruder)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 403)
        self.assertFalse(TournamentPlayerRegistration.objects.exists())

    def test_owner_can_add_and_duplicate_jersey_rejected(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, self.payload)
        self.assertEqual(TournamentPlayerRegistration.objects.count(), 1)
        resp = self.client.post(self.url, dict(self.payload, first_name='C'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TournamentPlayerRegistration.objects.count(), 1)


class TeamRegistrationTests(Base):
    def test_register_own_team(self):
        t = f.make_tournament()
        self.login(self.manager)
        self.client.post(reverse('tournaments:register_team', args=[t.slug]), {'confirm': 'on'})
        reg = TournamentTeamRegistration.objects.get(tournament=t)
        self.assertEqual((reg.team, reg.status), (self.team, 'pending'))
        self.client.post(reverse('tournaments:register_team', args=[t.slug]), {'confirm': 'on'})
        self.assertEqual(TournamentTeamRegistration.objects.filter(tournament=t).count(), 1)

    def test_register_players_respects_squad_limit(self):
        self.t.max_squad_size = 1
        self.t.save()
        p1, p2 = f.make_player(self.team), f.make_player(self.team)
        self.login(self.manager)
        self.client.post(reverse('tournaments:register_players', args=[self.t.slug]), {'players': [p1.pk, p2.pk]})
        self.assertFalse(TournamentPlayerRegistration.objects.exists())

    def test_review_cannot_exceed_capacity(self):
        t = f.make_tournament(max_teams=2)
        f.make_league_reg(t)
        f.make_league_reg(t)
        pending = f.make_league_reg(t, status='pending')
        self.login(self.admin)
        self.client.post(reverse('tournaments:review_registration', args=[pending.pk]), {'status': 'approved'})
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'pending')


class SquadTests(Base):
    def setUp(self):
        self.gk = f.make_player(self.team, position='GK')
        self.outfield = [f.make_player(self.team) for _ in range(7)]
        self.url = reverse('tournaments:tournament_submit_squad', args=[self.match.pk])

    def post(self, starting, subs=()):
        return self.client.post(self.url, {'starting_players': [p.pk for p in starting],
                                           'substitute_players': [p.pk for p in subs]})

    def test_get_does_not_create_squad(self):
        self.login(self.manager)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertFalse(TournamentMatchdaySquad.objects.exists())

    def test_submit_valid_squad(self):
        self.login(self.manager)
        self.post([self.gk, *self.outfield[:6]], self.outfield[6:])
        squad = TournamentMatchdaySquad.objects.get()
        self.assertEqual((squad.team_registration, squad.status), (self.reg, 'submitted'))
        self.assertEqual(squad.squad_players.filter(is_starting=True).count(), 7)
        self.assertEqual(squad.squad_players.filter(is_starting=False).count(), 1)

    def test_resubmission_replaces_not_duplicates(self):
        self.login(self.manager)
        self.post([self.gk, *self.outfield[:6]], self.outfield[6:])
        self.post([self.gk, *self.outfield[:6]])
        self.assertEqual(TournamentMatchdaySquad.objects.get().squad_players.count(), 7)

    def test_other_teams_players_rejected(self):
        """Security regression: arbitrary player IDs (other clubs) were accepted."""
        foreign = f.make_player(self.other_team)
        self.login(self.manager)
        self.post([self.gk, *self.outfield[:5], foreign])
        self.assertFalse(TournamentMatchdaySquad.objects.exists())

    def test_invalid_id_is_not_a_server_error(self):
        """Regression: non-existent IDs raised DoesNotExist (500)."""
        self.login(self.manager)
        resp = self.client.post(self.url, {'starting_players': ['999999', 'abc'] + [p.pk for p in self.outfield[:5]]})
        self.assertEqual(resp.status_code, 200)

    def test_goalkeeper_required(self):
        self.login(self.manager)
        self.post(self.outfield[:7])
        self.assertFalse(TournamentMatchdaySquad.objects.exists())

    def test_manager_of_non_participating_team_cannot_submit(self):
        outsider = f.make_user('Team Managers')
        f.make_team(manager=outsider)
        self.login(outsider)
        self.post([self.gk, *self.outfield[:6]])
        self.assertFalse(TournamentMatchdaySquad.objects.exists())

    def test_locked_after_kickoff(self):
        self.match.match_date = timezone.now() - timedelta(hours=1)
        self.match.save()
        self.login(self.manager)
        self.post([self.gk, *self.outfield[:6]])
        self.assertFalse(TournamentMatchdaySquad.objects.exists())


class SquadApprovalTests(Base):
    def setUp(self):
        self.squad = TournamentMatchdaySquad.objects.create(
            match=self.match, team_registration=self.reg, status='submitted',
        )
        self.url = reverse('tournaments:tournament_approve_squad', args=[self.squad.pk])

    def test_unappointed_referee_forbidden(self):
        """Security regression: any referee could approve any squad."""
        self.login(self.referee_user)
        self.assertEqual(self.client.post(self.url, {'action': 'approve'}).status_code, 403)
        self.squad.refresh_from_db()
        self.assertEqual(self.squad.status, 'submitted')

    def test_appointed_referee_approves(self):
        f.appoint(self.match, self.referee)
        self.login(self.referee_user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url, {'action': 'approve'})
        self.squad.refresh_from_db()
        self.assertEqual((self.squad.status, self.squad.approved_by), ('approved', self.referee))

    def test_reject_returns_to_pending(self):
        f.appoint(self.match, self.referee)
        self.login(self.referee_user)
        self.client.post(self.url, {'action': 'reject'})
        self.squad.refresh_from_db()
        self.assertEqual(self.squad.status, 'pending')


class AdminWorkflowTests(Base):
    def test_record_result_updates_standings(self):
        t = f.make_tournament(format='round_robin')
        a, b = f.make_league_reg(t), f.make_league_reg(t)
        self.login(self.admin)
        self.client.post(reverse('tournaments:generate_fixtures', args=[t.slug]),
                         {'first_match_date': '2030-01-01T15:00', 'days_between_rounds': 7})
        m = t.matches.get()
        self.client.post(reverse('tournaments:record_result', args=[m.pk]), {'home_score': 2, 'away_score': 0})
        m.refresh_from_db()
        self.assertEqual(m.status, 'completed')
        top = t.groups.get().standings.first()
        self.assertEqual((top.team_registration_id, top.points), (m.home_team_id, 3))
        # Populated public pages render (standings used to iterate a manager).
        for name in ('tournament_standings', 'tournament_fixtures', 'tournament_detail'):
            resp = self.client.get(reverse(f'tournaments:{name}', args=[t.slug]))
            self.assertEqual(resp.status_code, 200, name)
        self.assertContains(self.client.get(reverse('tournaments:tournament_standings', args=[t.slug])),
                            a.display_name if top.team_registration_id == a.pk else b.display_name)

    def test_referee_pages_render_with_squads(self):
        f.appoint(self.match, self.referee)
        squad = TournamentMatchdaySquad.objects.create(match=self.match, team_registration=self.reg,
                                                       status='submitted')
        self.login(self.referee_user)
        resp = self.client.get(reverse('tournaments:tournament_referee_squad_list'))
        self.assertContains(resp, reverse('tournaments:tournament_approve_squad', args=[squad.pk]))

    def test_regeneration_requires_confirmation(self):
        t = f.make_tournament(format='round_robin')
        f.make_league_reg(t), f.make_league_reg(t)
        url = reverse('tournaments:generate_fixtures', args=[t.slug])
        data = {'first_match_date': '2030-01-01T15:00', 'days_between_rounds': 7}
        self.login(self.admin)
        self.client.post(url, data)
        first_pk = t.matches.get().pk
        self.client.post(url, data)  # not confirmed: nothing changes
        self.assertEqual(t.matches.get().pk, first_pk)
        self.client.post(url, {**data, 'replace_existing': 'on'})
        self.assertNotEqual(t.matches.get().pk, first_pk)

    def test_drawn_knockout_needs_penalties(self):
        m = f.make_match(self.t, self.reg, self.other_reg, stage='semi_final')
        self.login(self.admin)
        url = reverse('tournaments:record_result', args=[m.pk])
        self.client.post(url, {'home_score': 1, 'away_score': 1})
        m.refresh_from_db()
        self.assertEqual(m.status, 'scheduled')
        self.client.post(url, {'home_score': 1, 'away_score': 1, 'home_penalties': 4, 'away_penalties': 2})
        m.refresh_from_db()
        self.assertEqual(m.status, 'completed')

    def test_result_needs_both_teams(self):
        m = f.make_match(self.t, stage='final')
        self.login(self.admin)
        self.client.post(reverse('tournaments:record_result', args=[m.pk]), {'home_score': 1, 'away_score': 0})
        m.refresh_from_db()
        self.assertEqual(m.status, 'scheduled')

    def test_appoint_officials_rejects_duplicate_referee(self):
        self.login(self.ref_manager)
        url = reverse('tournaments:appoint_officials', args=[self.match.pk])
        self.client.post(url, {'main_referee': self.referee.pk, 'assistant_1': self.referee.pk})
        self.assertFalse(TournamentMatchOfficials.objects.exists())
        self.client.post(url, {'main_referee': self.referee.pk})
        off = TournamentMatchOfficials.objects.get()
        self.assertEqual((off.status, off.appointed_by), ('APPOINTED', self.ref_manager))

    def test_edit_match_validates_input(self):
        """Regression: non-numeric durations raised ValueError (500)."""
        self.login(self.admin)
        url = reverse('tournaments:edit_tournament_match', args=[self.match.pk])
        resp = self.client.post(url, {'match_date': '2030-01-01T15:00', 'match_duration': 'abc',
                                      'half_duration': 45, 'extra_time_duration': 30})
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(url, {'match_date': '2030-01-01T15:00', 'match_duration': 70,
                                      'half_duration': 35, 'extra_time_duration': 20,
                                      'home_team': self.reg.pk, 'away_team': self.other_reg.pk,
                                      'kickoff_time': '15:30'})
        self.assertEqual(resp.status_code, 302)
        self.match.refresh_from_db()
        self.assertEqual((self.match.match_duration, self.match.kickoff_time), (70, '15:30'))

    def test_create_match_duplicate_number_is_form_error(self):
        self.login(self.admin)
        url = reverse('tournaments:create_match', args=[self.t.slug])
        data = {'stage': 'group', 'match_number': self.match.match_number,
                'match_date': '2030-01-01T15:00'}
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertEqual(TournamentMatch.objects.count(), 1)
