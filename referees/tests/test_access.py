"""URL-level access control for every referees URL."""
from django.test import TestCase
from django.urls import reverse

from referees.models import MatchReport, PreMatchMeetingForm

from . import factories as f

MANAGER_ONLY_GET = [
    ('referees:admin_referee_dashboard', {}),
    ('referees:pending_referees', {}),
    ('referees:all_referees', {}),
    ('referees:pending_reports', {}),
    ('referees:pending_prematch_forms_manager', {}),
    ('referees:matches_needing_officials', {}),
    ('referees:api_urgent_matches', {}),
    ('referees:api_appointed_matches', {}),
    ('referees:api_available_referees_today', {}),
    ('referees:generate_weekly_report', {}),
    ('referees:weekly_report_display', {}),
    ('referees:export_appointments_excel', {}),
]


class AccessMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = f.referees_manager()
        cls.team_manager = f.user('Team Managers')
        cls.ref = f.referee()
        cls.match = f.match()
        cls.report = MatchReport.objects.create(
            match=cls.match, referee=cls.ref, status=MatchReport.Status.SUBMITTED,
        )
        cls.pending_ref = f.referee(status='pending', with_user=False)
        cls.prematch = PreMatchMeetingForm.objects.create(
            match=cls.match, referee=cls.ref, match_date=cls.match.match_date.date(),
            home_team='H', away_team='A', venue='V', status=PreMatchMeetingForm.Status.SUBMITTED,
        )

    def all_urls(self):
        m, r, rid, pf = self.match.id, self.report.id, self.pending_ref.id, self.prematch.id
        names = {
            'referee_dashboard': {}, 'referee_profile': {}, 'referee_availability': {},
            'view_report': {'report_id': r}, 'confirm_appointment': {'match_id': m},
            'decline_appointment': {'match_id': m}, 'submit_match_report': {'match_id': m},
            'submit_comprehensive_report': {'match_id': m}, 'cancel_appointment': {'match_id': m},
            'team_matchday_squad_list': {}, 'submit_matchday_squad': {'match_id': m},
            'team_request_squad_edit': {'match_id': m}, 'team_request_substitution': {'match_id': m},
            'referee_squad_approval_list': {}, 'approve_matchday_squads': {'match_id': m},
            'referee_review_edit_requests': {}, 'reserve_referee_substitutions': {'match_id': m},
            'activate_concussion_substitute': {'match_id': m}, 'pending_reports': {},
            'approve_report': {'report_id': r}, 'reject_report': {'report_id': r},
            'report_detail_view': {'report_id': r}, 'submit_prematch_form': {'match_id': m},
            'view_prematch_form': {'form_id': pf}, 'admin_approve_prematch_form': {'form_id': pf},
            'manager_approve_prematch_form': {'form_id': pf}, 'pending_prematch_forms_admin': {},
            'pending_prematch_forms_manager': {}, 'matches_needing_officials': {},
            'appoint_match_officials': {'match_id': m}, 'replace_referee': {'match_id': m, 'role': 'AR1'},
            'admin_referee_dashboard': {}, 'pending_referees': {}, 'all_referees': {},
            'approve_referee': {'referee_id': rid}, 'reject_referee': {'referee_id': rid},
            'suspend_referee': {'referee_id': rid}, 'reactivate_referee': {'referee_id': rid},
            'api_urgent_matches': {}, 'api_appointed_matches': {}, 'api_available_referees_today': {},
            'generate_weekly_report': {}, 'weekly_report_display': {}, 'export_appointments_excel': {},
        }
        return [reverse('referees:' + k, kwargs=v) for k, v in names.items()]

    def test_anonymous_is_sent_to_login_everywhere_except_public_pages(self):
        for url in self.all_urls():
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertIn(resp.status_code, (302, 405))
                if resp.status_code == 302:
                    self.assertIn('/accounts/login/', resp['Location'])

    def test_public_pages(self):
        for name in ('referees:referee_registration', 'referees:login_instructions'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_manager_pages_forbidden_for_team_manager_and_referee(self):
        for u in (self.team_manager, self.ref.user):
            self.client.force_login(u)
            for name, kwargs in MANAGER_ONLY_GET:
                with self.subTest(user=u.username, url=name):
                    self.assertEqual(self.client.get(reverse(name, kwargs=kwargs)).status_code, 403)

    def test_manager_pages_ok_for_referees_manager(self):
        self.client.force_login(self.manager)
        for name, kwargs in MANAGER_ONLY_GET:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name, kwargs=kwargs)).status_code, 200)

    def test_manager_detail_pages(self):
        self.client.force_login(self.manager)
        for name, kw in [
            ('referees:report_detail_view', {'report_id': self.report.id}),
            ('referees:approve_report', {'report_id': self.report.id}),
            ('referees:reject_report', {'report_id': self.report.id}),
            ('referees:approve_referee', {'referee_id': self.pending_ref.id}),
            ('referees:reject_referee', {'referee_id': self.pending_ref.id}),
            ('referees:view_prematch_form', {'form_id': self.prematch.id}),
            ('referees:appoint_match_officials', {'match_id': self.match.id}),
            ('referees:submit_comprehensive_report', {'match_id': self.match.id}),
        ]:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name, kwargs=kw)).status_code, 200)

    def test_referee_self_service_pages(self):
        self.client.force_login(self.ref.user)
        for name in ('referees:referee_dashboard', 'referees:referee_profile', 'referees:referee_availability',
                     'referees:referee_squad_approval_list', 'referees:referee_review_edit_requests'):
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse('referees:view_report', args=[self.report.id])).status_code, 200)

    def test_other_referee_cannot_view_report(self):
        self.client.force_login(f.referee().user)
        self.assertEqual(self.client.get(reverse('referees:view_report', args=[self.report.id])).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('referees:report_detail_view', args=[self.report.id])).status_code, 403,
        )
        self.assertEqual(
            self.client.get(reverse('referees:view_prematch_form', args=[self.prematch.id])).status_code, 403,
        )

    def test_league_admin_sees_admin_prematch_queue_only(self):
        self.client.force_login(f.user('League Admin'))
        self.assertEqual(self.client.get(reverse('referees:pending_prematch_forms_admin')).status_code, 200)
        self.assertEqual(self.client.get(reverse('referees:pending_prematch_forms_manager')).status_code, 403)

    def test_post_only_endpoints_reject_get(self):
        self.client.force_login(self.manager)
        for name, kw in [
            ('referees:suspend_referee', {'referee_id': self.ref.id}),
            ('referees:reactivate_referee', {'referee_id': self.ref.id}),
            ('referees:activate_concussion_substitute', {'match_id': self.match.id}),
        ]:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name, kwargs=kw)).status_code, 405)
