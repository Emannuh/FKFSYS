from django.test import TestCase
from django.urls import reverse

from teams.models import Player, TransferHistory, TransferRequest

from .factories import make_manager_with_team, make_player, make_transfer, make_user, open_windows


class TransferWorkflowTests(TestCase):
    def setUp(self):
        open_windows()
        self.buyer, self.buyer_team = make_manager_with_team()
        self.seller, self.seller_team = make_manager_with_team()
        self.player = make_player(self.seller_team, jersey=10, is_captain=True)

    def _request(self, user=None, player=None):
        self.client.force_login(user or self.buyer)
        return self.client.post(reverse('teams:request_transfer', args=[(player or self.player).pk]))

    def test_request_creates_pending_transfer(self):
        resp = self._request()
        self.assertRedirects(resp, reverse('teams:my_transfer_requests'))
        tr = TransferRequest.objects.get()
        self.assertEqual((tr.from_team, tr.to_team, tr.status), (self.seller_team, self.buyer_team, 'pending_parent'))

    def test_duplicate_request_rejected(self):
        self._request()
        self._request()
        self.assertEqual(TransferRequest.objects.count(), 1)

    def test_cannot_request_own_player(self):
        own = make_player(self.buyer_team, jersey=3)
        self._request(player=own)
        self.assertFalse(TransferRequest.objects.exists())

    def test_request_blocked_when_window_closed(self):
        open_windows(transfer_window_open=False)
        resp = self._request()
        self.assertContains(resp, 'Transfer Window Closed')
        self.assertFalse(TransferRequest.objects.exists())

    def test_parent_club_approves_and_player_moves(self):
        make_player(self.buyer_team, jersey=10)  # jersey clash on destination
        tr = make_transfer(self.player, self.buyer_team, self.buyer)
        self.client.force_login(self.seller)
        resp = self.client.post(reverse('teams:approve_transfer', args=[tr.pk]))
        self.assertRedirects(resp, reverse('teams:my_transfer_requests'))
        self.player.refresh_from_db()
        tr.refresh_from_db()
        self.assertEqual(tr.status, 'approved')
        self.assertEqual(self.player.team, self.buyer_team)
        self.assertNotEqual(self.player.jersey_number, 10)
        self.assertFalse(self.player.is_captain)
        self.assertTrue(TransferHistory.objects.filter(transfer_request=tr, approved_by=self.seller).exists())

    def test_requester_cannot_approve_own_request(self):
        """IDOR regression: only the parent club may approve."""
        tr = make_transfer(self.player, self.buyer_team, self.buyer)
        self.client.force_login(self.buyer)
        resp = self.client.post(reverse('teams:approve_transfer', args=[tr.pk]))
        self.assertEqual(resp.status_code, 403)
        tr.refresh_from_db()
        self.assertEqual(tr.status, 'pending_parent')
        self.assertEqual(Player.objects.get(pk=self.player.pk).team, self.seller_team)

    def test_third_party_cannot_approve_reject_or_cancel(self):
        intruder, _ = make_manager_with_team()
        tr = make_transfer(self.player, self.buyer_team, self.buyer)
        self.client.force_login(intruder)
        self.assertEqual(self.client.post(reverse('teams:approve_transfer', args=[tr.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('teams:cancel_transfer', args=[tr.pk])).status_code, 403)
        self.client.post(reverse('teams:reject_transfer', args=[tr.pk]), {'reason': 'x'})
        tr.refresh_from_db()
        self.assertEqual(tr.status, 'pending_parent')

    def test_non_manager_cannot_approve(self):
        tr = make_transfer(self.player, self.buyer_team, self.buyer)
        self.client.force_login(make_user('Referee'))
        self.assertEqual(self.client.post(reverse('teams:approve_transfer', args=[tr.pk])).status_code, 403)

    def test_double_approval_is_idempotent(self):
        tr = make_transfer(self.player, self.buyer_team, self.buyer)
        self.client.force_login(self.seller)
        self.client.post(reverse('teams:approve_transfer', args=[tr.pk]))
        self.client.post(reverse('teams:approve_transfer', args=[tr.pk]))
        self.assertEqual(TransferHistory.objects.count(), 1)

    def test_stale_request_cannot_move_player_back(self):
        """Regression: after a player moves, an old request's from_team could still 'approve' it."""
        third, third_team = make_manager_with_team()
        first = make_transfer(self.player, self.buyer_team, self.buyer)
        second = make_transfer(self.player, third_team, third)
        self.client.force_login(self.seller)
        self.client.post(reverse('teams:approve_transfer', args=[first.pk]))
        second.refresh_from_db()
        self.assertEqual(second.status, 'cancelled')  # auto-cancelled on execution
        self.client.post(reverse('teams:approve_transfer', args=[second.pk]))
        self.player.refresh_from_db()
        self.assertEqual(self.player.team, self.buyer_team)

    def test_reject_requires_reason_and_is_post_only_mutation(self):
        tr = make_transfer(self.player, self.buyer_team, self.buyer)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(reverse('teams:reject_transfer', args=[tr.pk])).status_code, 200)
        self.client.post(reverse('teams:reject_transfer', args=[tr.pk]), {'reason': '   '})
        tr.refresh_from_db()
        self.assertEqual(tr.status, 'pending_parent')
        self.client.post(reverse('teams:reject_transfer', args=[tr.pk]), {'reason': 'Key player'})
        tr.refresh_from_db()
        self.assertEqual((tr.status, tr.parent_decision_reason), ('rejected', 'Key player'))

    def test_requester_can_cancel_pending(self):
        tr = make_transfer(self.player, self.buyer_team, self.buyer)
        self.client.force_login(self.buyer)
        self.client.post(reverse('teams:cancel_transfer', args=[tr.pk]))
        tr.refresh_from_db()
        self.assertEqual(tr.status, 'cancelled')

    def test_admin_override_records_admin_as_approver(self):
        tr = make_transfer(self.player, self.buyer_team, self.buyer)
        tr.reject_by_parent(self.seller, 'no')
        admin = make_user(superuser=True)
        tr.override_by_admin(admin, 'override')
        self.assertEqual(TransferHistory.objects.get().approved_by, admin)

    def test_search_hides_identity_documents(self):
        """PII regression: other clubs' players' ID numbers / DOB were listed."""
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('teams:search_players'), {'team_id': self.seller_team.pk})
        self.assertContains(resp, self.player.full_name)
        self.assertNotContains(resp, self.player.id_number)
