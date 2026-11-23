"""The audit trail: single writer, append-only, scrubbed, never breaks requests."""
from unittest import mock

from django.contrib.admin.sites import site
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from ..activity_logger import MASK, get_client_ip, log_activity, scrub
from ..activity_middleware import classify
from ..models import ActivityLog, AuditLogImmutableError
NON_LOGIN = ActivityLog.objects.exclude(action='LOGIN')

from .factories import ensure_groups, make_superuser, make_team, make_user


class LogActivityTests(TestCase):
    def test_scrub_masks_secrets_and_pii(self):
        data = scrub({'password': 'x', 'phone_number': '0700', 'nested': {'id_number': '1'}, 'zone_id': 3})
        self.assertEqual(data, {'password': MASK, 'phone_number': MASK, 'nested': {'id_number': MASK}, 'zone_id': 3})

    def test_log_activity_records_object_and_request_metadata(self):
        user = make_user()
        team = make_team()
        request = RequestFactory().post('/x/', REMOTE_ADDR='10.0.0.5', HTTP_USER_AGENT='UA')
        entry = log_activity(user, ActivityLog.Action.TEAM_APPROVE, 'Approved', obj=team, request=request,
                             extra_data={'token': 'secret'})
        self.assertEqual(entry.object_id, team.pk)
        self.assertEqual(entry.ip_address, '10.0.0.5')
        self.assertEqual(entry.extra_data, {'token': MASK})
        self.assertTrue(request._audit_logged)

    def test_log_activity_never_raises(self):
        with mock.patch.object(ActivityLog, 'save', side_effect=RuntimeError('db down')):
            with self.assertLogs('admin_dashboard.audit', 'ERROR'):
                self.assertIsNone(log_activity(None, 'OTHER', 'x'))

    def test_forwarded_for_ignored_unless_behind_proxy(self):
        request = RequestFactory().get('/', REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR='1.2.3.4')
        with override_settings(AUDIT_TRUST_X_FORWARDED_FOR=False):
            self.assertEqual(get_client_ip(request), '10.0.0.1')
        with override_settings(AUDIT_TRUST_X_FORWARDED_FOR=True):
            self.assertEqual(get_client_ip(request), '1.2.3.4')
        bad = RequestFactory().get('/', REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR='<script>')
        with override_settings(AUDIT_TRUST_X_FORWARDED_FOR=True):
            self.assertEqual(get_client_ip(bad), '10.0.0.1')


class AppendOnlyTests(TestCase):
    def setUp(self):
        self.entry = log_activity(None, 'OTHER', 'x')

    def test_rows_cannot_be_modified_or_deleted(self):
        self.entry.description = 'tampered'
        with self.assertRaises(AuditLogImmutableError):
            self.entry.save()
        with self.assertRaises(AuditLogImmutableError):
            self.entry.delete()
        with self.assertRaises(AuditLogImmutableError):
            ActivityLog.objects.filter(pk=self.entry.pk).update(description='t')
        with self.assertRaises(AuditLogImmutableError):
            ActivityLog.objects.all().delete()

    def test_deleting_actor_keeps_log(self):
        user = make_user()
        entry = log_activity(user, 'OTHER', 'by user')
        user.delete()
        entry = ActivityLog.objects.get(pk=entry.pk)
        self.assertIsNone(entry.user)

    def test_django_admin_is_read_only(self):
        model_admin = site._registry[ActivityLog]
        request = RequestFactory().get('/')
        request.user = make_superuser()
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request, self.entry))
        self.assertFalse(model_admin.has_delete_permission(request, self.entry))
        self.assertNotIn('changes_json', model_admin.fields)


class MiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.admin = make_user('League Admin')
        cls.team_manager = make_user('Team Managers')

    def test_classify(self):
        self.assertEqual(classify('/admin-dashboard/generate-fixtures/'), 'FIXTURE_GENERATE')
        self.assertEqual(classify('/teams/player/add/'), 'PLAYER_CREATE')
        # regression: 'approve' anywhere used to be logged as SQUAD_APPROVE
        self.assertEqual(classify('/admin-dashboard/approve-registrations/'), 'ADMIN_ACTION')

    def test_generic_post_logs_field_names_not_values(self):
        self.client.force_login(self.admin)
        # Unknown action: view doesn't write an explicit entry, middleware does.
        self.client.post(reverse('admin_dashboard:toggle_registration'),
                         {'window_type': 'nope', 'phone_number': '0712345678'})
        entry = NON_LOGIN.get(action='ADMIN_ACTION')
        self.assertEqual(entry.extra_data['url_name'], 'admin_dashboard:toggle_registration')
        self.assertIn('phone_number', entry.extra_data['fields'])
        self.assertNotIn('0712345678', str(entry.extra_data) + entry.description + entry.changes_json)

    def test_explicitly_logged_request_not_duplicated(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_dashboard:toggle_registration'), {'window_type': 'team'})
        self.assertEqual(NON_LOGIN.count(), 1)
        self.assertEqual(NON_LOGIN.get().action, 'REGISTRATION_TOGGLE')

    def test_denied_post_logged_as_access_denied(self):
        self.client.force_login(self.team_manager)
        self.client.post(reverse('admin_dashboard:toggle_registration'), {'window_type': 'team'})
        self.assertEqual(NON_LOGIN.get().action, 'ACCESS_DENIED')

    def test_get_requests_not_logged(self):
        self.client.force_login(self.admin)
        self.client.get(reverse('admin_dashboard:statistics_dashboard'))
        self.assertFalse(NON_LOGIN.exists())

    def test_logging_failure_does_not_break_request(self):
        self.client.force_login(self.admin)
        with mock.patch.object(ActivityLog, 'save', side_effect=RuntimeError('db down')), \
                self.assertLogs('admin_dashboard.audit', 'ERROR'):
            resp = self.client.post(reverse('admin_dashboard:toggle_registration'), {'window_type': 'team'})
        self.assertEqual(resp.status_code, 302)


class AuthSignalTests(TestCase):
    def test_login_logout_and_failed_login_are_logged(self):
        user = make_user(password='Corr3ct-horse!')
        self.client.post(reverse('login'), {'username': user.username, 'password': 'wrong-pass'})
        self.client.post(reverse('login'), {'username': user.username, 'password': 'Corr3ct-horse!'})
        self.client.post(reverse('logout'))
        actions = list(ActivityLog.objects.order_by('timestamp', 'id').values_list('action', flat=True))
        self.assertEqual(actions, ['LOGIN_FAILED', 'LOGIN', 'LOGOUT'])
        failed = ActivityLog.objects.get(action='LOGIN_FAILED')
        self.assertEqual(failed.extra_data, {'attempted_username': user.username})
        self.assertNotIn('wrong-pass', str(failed.extra_data) + failed.description)
