"""Superuser user/role management."""
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from ..models import ActivityLog
from .factories import User, ensure_groups, make_superuser, make_user


class UserManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.superuser = make_superuser()
        cls.other_superuser = make_superuser()

    def setUp(self):
        self.client.force_login(self.superuser)

    def url(self, name, *args):
        return reverse(f'admin_dashboard:{name}', args=args)

    def test_create_user_emails_link_not_password(self):
        resp = self.client.post(self.url('create_league_admin'), {
            'username': 'newadmin', 'email': 'new@example.test', 'first_name': 'N', 'last_name': 'A',
            'role': 'League Admin',
        })
        self.assertRedirects(resp, self.url('manage_league_admins'), fetch_redirect_response=False)
        user = User.objects.get(username='newadmin')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.groups.filter(name='League Admin').exists())
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('/accounts/reset/', body)
        self.assertNotIn('Password:', body)
        log = ActivityLog.objects.get(action='USER_CREATE')
        self.assertEqual(log.user, self.superuser)
        self.assertEqual(log.object_id, user.pk)

    def test_create_user_rejects_unknown_role(self):
        self.client.post(self.url('create_league_admin'), {
            'username': 'x1', 'email': 'x1@example.test', 'role': 'Superusers'})
        self.assertFalse(User.objects.filter(username='x1').exists())
        self.assertFalse(Group.objects.filter(name='Superusers').exists())

    def test_cannot_deactivate_self_or_superuser(self):
        self.client.post(self.url('toggle_league_admin_status', self.superuser.id))
        self.client.post(self.url('toggle_league_admin_status', self.other_superuser.id))
        self.superuser.refresh_from_db()
        self.other_superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active and self.other_superuser.is_active)

    def test_toggle_user_is_logged(self):
        target = make_user()
        self.client.post(self.url('toggle_league_admin_status', target.id))
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertTrue(ActivityLog.objects.filter(action='USER_DEACTIVATE', object_id=target.pk).exists())

    def test_reset_password_invalidates_and_emails_link(self):
        target = make_user()
        self.client.post(self.url('reset_league_admin_password', target.id))
        target.refresh_from_db()
        self.assertFalse(target.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)
        self.assertTrue(ActivityLog.objects.filter(action='PASSWORD_RESET', object_id=target.pk).exists())

    def test_cannot_reset_own_password_here(self):
        self.client.post(self.url('reset_league_admin_password', self.superuser.id))
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.has_usable_password())

    def test_edit_roles_replaces_groups_and_logs_diff(self):
        target = make_user('Referee')
        self.client.post(self.url('edit_user_roles', target.id), {'groups': ['League Admin']})
        self.assertEqual(list(target.groups.values_list('name', flat=True)), ['League Admin'])
        log = ActivityLog.objects.get(action='USER_ROLE_CHANGE')
        self.assertEqual(log.extra_data, {'before': ['Referee'], 'after': ['League Admin']})
        target.refresh_from_db()
        self.assertFalse(target.is_staff or target.is_superuser)

    def test_edit_roles_unknown_group_is_rejected_not_500(self):
        target = make_user('Referee')
        resp = self.client.post(self.url('edit_user_roles', target.id), {'groups': ['Nope']})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(list(target.groups.values_list('name', flat=True)), ['Referee'])

    def test_delete_user(self):
        target = make_user()
        self.client.post(self.url('delete_user', target.id))
        self.assertFalse(User.objects.filter(pk=target.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(action='USER_DELETE', description__contains=target.username).exists())

    def test_cannot_delete_superuser(self):
        self.client.post(self.url('delete_user', self.other_superuser.id))
        self.assertTrue(User.objects.filter(pk=self.other_superuser.pk).exists())

    def test_user_list_renders_paginated(self):
        resp = self.client.get(self.url('manage_league_admins'), {'search': 'user'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'method="post"')
