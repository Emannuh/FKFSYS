"""Redesigned referees templates render with real data and keep the markup their forms/JS rely on."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from referees.models import MatchReport, PreMatchMeetingForm, StartingLineup

from . import factories as f


class RefereeTemplateRenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = f.referees_manager()
        cls.ref = f.referee()
        cls.ar = f.referee()
        home = f.team()
        cls.home, cls.away = home, f.team(z=home.zone)
        cls.match = f.match(cls.home, cls.away)
        cls.past = f.match(f.team(z=home.zone), f.team(z=home.zone), when=timezone.now() - timedelta(days=2))
        f.officials(cls.match, main_referee=cls.ref, assistant_1=cls.ar)
        f.officials(cls.past, main_referee=cls.ref, assistant_1=cls.ar, main_confirmed=True)
        cls.report = MatchReport.objects.create(match=cls.past, referee=cls.ref, status=MatchReport.Status.DRAFT)

    def get(self, user, name, status=200, **kwargs):
        self.client.force_login(user)
        resp = self.client.get(reverse('referees:' + name, kwargs=kwargs))
        self.assertEqual(resp.status_code, status, name)
        return resp

    # --- referee self-service -------------------------------------------------
    def test_dashboard(self):
        resp = self.get(self.ref.user, 'referee_dashboard')
        self.assertContains(resp, 'id="pending-section"')
        self.assertContains(resp, reverse('referees:confirm_appointment', args=[self.match.id]))
        self.assertContains(resp, 'id="assignmentsChart"')
        self.assertContains(resp, 'id="reports-section"')
        self.assertContains(resp, 'css/pages/referees.css')

    def test_availability(self):
        resp = self.get(self.ref.user, 'referee_availability')
        for marker in ('id="availabilityForm"', 'name="is_available"', 'id="calendarDays"', 'id="deleteForm"',
                       'class="btn btn-outline-secondary quick-date"'):
            self.assertContains(resp, marker)
        self.assertNotContains(resp, 'data-date=""')

    # --- reports --------------------------------------------------------------
    def test_comprehensive_report_formsets(self):
        StartingLineup.objects.create(match=self.past, team=self.past.home_team,
                                      player=f.player(self.past.home_team), jersey_number=4)
        resp = self.get(self.ref.user, 'submit_comprehensive_report', match_id=self.past.id)
        for marker in ('id="id_goal-TOTAL_FORMS"', 'id="id_card-TOTAL_FORMS"', 'id="id_starting-TOTAL_FORMS"',
                       'id="id_reserve-TOTAL_FORMS"', 'id="empty-goal"', 'id="empty-card"',
                       '<template id="empty-starting-home">', '<template id="empty-reserve-away">',
                       'id="add-home-starting"', 'id="add-away-reserves"', 'name="save_draft"',
                       'name="submit_report"', 'name="submit_score"', 'name="match_number"', 'name="league_level"', 'name="starting-0-DELETE"'):
            self.assertContains(resp, marker)
        self.assertContains(resp, 'id="home-starting-lineup"')

    def test_comprehensive_report_draft_saves_header_fields(self):
        self.client.force_login(self.ref.user)
        url = reverse('referees:submit_comprehensive_report', args=[self.past.id])
        data = {'save_draft': '1', 'match_number': 'M-77', 'round_number': '3', 'league_level': 'FKF County League',
                'penalties_not_converted': '', 'serious_incidents': '', 'referee_comments': 'ok'}
        for prefix in ('goal', 'card', 'starting', 'reserve'):
            data.update({f'{prefix}-TOTAL_FORMS': '0', f'{prefix}-INITIAL_FORMS': '0',
                         f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000'})
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual((self.report.match_number, self.report.status), ('M-77', 'draft'))

    def test_comprehensive_report_read_only_for_assistant(self):
        resp = self.get(self.ar.user, 'submit_comprehensive_report', match_id=self.past.id)
        self.assertContains(resp, 'Viewing only')
        self.assertNotContains(resp, 'name="submit_report"')

    def test_flash_report(self):
        resp = self.get(self.ref.user, 'submit_match_report', match_id=self.past.id)
        for marker in ('id="flashReportForm"', 'id="id_matchgoal_set-TOTAL_FORMS"', 'id="id_caution_set-TOTAL_FORMS"',
                       'data-prefix="matchgoal_set"', '<template id="flashPlayers">', 'name="submit_flash_report"'):
            self.assertContains(resp, marker)
