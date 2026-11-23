"""Payments: Daraja client, callback verification, access control. No real network calls."""
import json
from decimal import Decimal
from unittest import mock

import requests
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from payments import services
from payments.daraja import DarajaClient, DarajaConfigError, DarajaError, callback_token, mask_phone
from payments.models import Payment
from teams.models import Team

MPESA = {
    "CONSUMER_KEY": "ck-test", "CONSUMER_SECRET": "cs-test", "SHORTCODE": "174379",
    "PASSKEY": "pk-test", "CALLBACK_URL": "https://example.test/anything/", "ENVIRONMENT": "sandbox",
}

_seq = iter(range(10_000))


def make_team(**kw):
    n = next(_seq)
    defaults = dict(
        team_name=f"Team {n}", location="Meru", home_ground="Ground", contact_person="C",
        phone_number=f"+2547{n:08d}", email=f"t{n}@example.test",
    )
    defaults.update(kw)
    return Team.objects.create(**defaults)


def fake_response(status=200, data=None):
    r = mock.Mock(status_code=status)
    r.json.return_value = data if data is not None else {}
    if status >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(f"{status}")
    else:
        r.raise_for_status.return_value = None
    return r


def callback_payload(payment, code=0, amount=None, receipt="QWE123RTY"):
    cb = {
        "MerchantRequestID": payment.merchant_request_id,
        "CheckoutRequestID": payment.checkout_request_id,
        "ResultCode": code,
        "ResultDesc": "ok" if code == 0 else "Request cancelled by user",
    }
    if code == 0:
        cb["CallbackMetadata"] = {"Item": [
            {"Name": "Amount", "Value": float(amount if amount is not None else payment.amount)},
            {"Name": "MpesaReceiptNumber", "Value": receipt},
            {"Name": "PhoneNumber", "Value": 254712345678},
        ]}
    return {"Body": {"stkCallback": cb}}


def make_pending(team=None, **kw):
    return Payment.objects.create(
        team=team or make_team(), amount=Decimal("16000"), phone_number="+254712345678",
        checkout_request_id=kw.pop("checkout", f"ws_CO_{next(_seq)}"),
        merchant_request_id=kw.pop("merchant", "m-1"), **kw,
    )


@override_settings(MPESA_CONFIG=MPESA)
class DarajaClientTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_environment_selects_base_url(self):
        self.assertIn("sandbox", DarajaClient().base_url)
        self.assertEqual(DarajaClient({**MPESA, "ENVIRONMENT": "production"}).base_url,
                         "https://api.safaricom.co.ke")
        with self.assertRaises(DarajaConfigError):
            DarajaClient({**MPESA, "ENVIRONMENT": "prod"})

    def test_missing_credentials_is_config_error(self):
        with self.assertRaises(DarajaConfigError):
            DarajaClient({**MPESA, "PASSKEY": ""})

    def test_production_requires_https_callback(self):
        c = DarajaClient({**MPESA, "ENVIRONMENT": "production", "CALLBACK_URL": "http://x.test/"})
        with self.assertRaises(DarajaConfigError):
            c.callback_url()

    def test_callback_url_uses_host_only_and_secret_token(self):
        url = DarajaClient().callback_url()
        self.assertEqual(url, f"https://example.test/payments/callback/{callback_token()}/")
        self.assertGreaterEqual(len(callback_token()), 64)

    @mock.patch("payments.daraja.requests")
    def test_token_cached_and_timeouts_set(self, req):
        req.RequestException = requests.RequestException
        req.get.return_value = fake_response(data={"access_token": "tok", "expires_in": "3599"})
        req.post.return_value = fake_response(data={"ResponseCode": "0", "CheckoutRequestID": "c1"})
        client = DarajaClient()
        client.stk_push("+254712345678", 16000, "REF", "desc")
        client.stk_push("+254712345678", 16000, "REF", "desc")
        self.assertEqual(req.get.call_count, 1)
        self.assertIn("timeout", req.get.call_args.kwargs)
        self.assertIn("timeout", req.post.call_args.kwargs)
        sent = req.post.call_args.kwargs["json"]
        self.assertEqual(sent["PhoneNumber"], "254712345678")
        self.assertTrue(sent["CallBackURL"].endswith(f"/{callback_token()}/"))

    @mock.patch("payments.daraja.requests")
    def test_network_error_raises_and_does_not_log_secrets(self, req):
        req.RequestException = requests.RequestException
        req.get.return_value = fake_response(data={"access_token": "tok-secret"})
        req.post.side_effect = requests.ConnectionError("boom")
        with self.assertLogs("payments.daraja", level="INFO") as logs, self.assertRaises(DarajaError):
            DarajaClient().stk_push("+254712345678", 16000, "REF", "desc")
        joined = "\n".join(logs.output)
        for secret in ("tok-secret", "pk-test", "cs-test", "ck-test", "254712345678"):
            self.assertNotIn(secret, joined)

    @mock.patch("payments.daraja.requests")
    def test_rejected_push_raises(self, req):
        req.RequestException = requests.RequestException
        req.get.return_value = fake_response(data={"access_token": "t"})
        req.post.return_value = fake_response(data={"ResponseCode": "1"})
        with self.assertRaises(DarajaError):
            DarajaClient().stk_push("+254712345678", 1, "R", "d")

    def test_mask_phone(self):
        self.assertEqual(mask_phone("+254712345678"), "2547******78")
        self.assertEqual(mask_phone(None), "***")


@override_settings(MPESA_CONFIG=MPESA)
class CallbackProcessingTests(TestCase):
    def setUp(self):
        self.payment = make_pending()
        self.url = reverse("payments:payment_callback", kwargs={"token": callback_token()})
        patcher = mock.patch.object(services, "_query_result_code", return_value=0)
        self.query = patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, payload, url=None):
        return self.client.post(url or self.url, data=json.dumps(payload), content_type="application/json")

    def test_success_marks_completed_and_team_paid(self):
        r = self.post(callback_payload(self.payment))
        self.assertEqual(r.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "completed")
        self.assertEqual(self.payment.mpesa_receipt_number, "QWE123RTY")
        self.payment.team.refresh_from_db()
        self.assertTrue(self.payment.team.payment_status)
        self.assertIsNotNone(self.payment.team.payment_date)

    def test_duplicate_callback_is_idempotent(self):
        self.assertEqual(services.process_stk_callback(callback_payload(self.payment)), "completed")
        self.assertEqual(services.process_stk_callback(callback_payload(self.payment)), "duplicate")
        # A later "failed" callback cannot undo a completed payment.
        self.assertEqual(services.process_stk_callback(callback_payload(self.payment, code=1032)), "duplicate")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "completed")

    def test_wrong_token_is_404_and_no_change(self):
        r = self.post(callback_payload(self.payment),
                      url=reverse("payments:payment_callback", kwargs={"token": "guess"}))
        self.assertEqual(r.status_code, 404)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_malformed_payload_400(self):
        self.assertEqual(self.post({"Body": "x"}).status_code, 400)
        r = self.client.post(self.url, data="not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_unknown_checkout_id_ignored(self):
        p = callback_payload(self.payment)
        p["Body"]["stkCallback"]["CheckoutRequestID"] = "ws_CO_forged"
        self.assertEqual(services.process_stk_callback(p), "unknown")

    def test_amount_mismatch_not_completed(self):
        # Regression: old code overwrote payment.amount with the callback value.
        out = services.process_stk_callback(callback_payload(self.payment, amount=1))
        self.assertEqual(out, "rejected")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")
        self.assertEqual(self.payment.amount, Decimal("16000"))
        self.payment.team.refresh_from_db()
        self.assertFalse(self.payment.team.payment_status)

    def test_merchant_id_mismatch_rejected(self):
        p = callback_payload(self.payment)
        p["Body"]["stkCallback"]["MerchantRequestID"] = "other"
        self.assertEqual(services.process_stk_callback(p), "rejected")

    def test_failure_result_marks_failed(self):
        self.assertEqual(services.process_stk_callback(callback_payload(self.payment, code=1032)), "failed")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")
        self.assertEqual(self.payment.result_code, 1032)

    def test_success_not_confirmed_by_query_stays_pending(self):
        self.query.return_value = None
        self.assertEqual(services.process_stk_callback(callback_payload(self.payment)), "unverified")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")
        self.assertEqual(self.payment.mpesa_receipt_number, "QWE123RTY")

    @override_settings(MPESA_CALLBACK_ALLOWED_IPS=["196.201.214.200"])
    def test_ip_allow_list(self):
        self.assertEqual(self.post(callback_payload(self.payment)).status_code, 403)


@override_settings(MPESA_CONFIG=MPESA)
class RefreshStatusTests(TestCase):
    def test_query_success_completes(self):
        p = make_pending()
        client = mock.Mock(query_status=mock.Mock(return_value={"ResultCode": "0"}))
        services.refresh_payment_status(p, client=client)
        self.assertEqual(p.status, "completed")

    def test_still_processing_keeps_pending(self):
        p = make_pending()
        client = mock.Mock(query_status=mock.Mock(side_effect=DarajaError("500")))
        services.refresh_payment_status(p, client=client)
        self.assertEqual(p.status, "pending")

    def test_cancelled_marks_failed(self):
        p = make_pending()
        client = mock.Mock(query_status=mock.Mock(return_value={"ResultCode": "1032"}))
        services.refresh_payment_status(p, client=client)
        self.assertEqual(p.status, "failed")

    def test_completed_payment_not_requeried(self):
        p = make_pending(status="completed")
        client = mock.Mock()
        services.refresh_payment_status(p, client=client)
        client.query_status.assert_not_called()


@override_settings(MPESA_CONFIG=MPESA)
class InitiationTests(TestCase):
    def test_creates_pending_payment(self):
        team = make_team()
        client = mock.Mock(stk_push=mock.Mock(return_value={"CheckoutRequestID": "c9", "MerchantRequestID": "m9"}))
        p = services.initiate_registration_payment(team, "+254712345678", client=client)
        self.assertEqual((p.status, p.amount, p.checkout_request_id), ("pending", Decimal("16000"), "c9"))

    def test_cooldown_blocks_spam(self):
        team = make_team()
        make_pending(team=team)
        with self.assertRaises(services.PaymentError):
            services.initiate_registration_payment(team, "+254712345678", client=mock.Mock())

    def test_already_paid_blocked(self):
        team = make_team(payment_status=True)
        with self.assertRaises(services.PaymentError):
            services.initiate_registration_payment(team, "+254712345678", client=mock.Mock())

    def test_daraja_failure_creates_nothing(self):
        team = make_team()
        client = mock.Mock(stk_push=mock.Mock(side_effect=DarajaError("x")))
        with self.assertRaises(services.PaymentError):
            services.initiate_registration_payment(team, "+254712345678", client=client)
        self.assertFalse(Payment.objects.exists())


@override_settings(MPESA_CONFIG=MPESA)
class PaymentViewAccessTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("mgr", password="pw")
        self.team = make_team(manager=self.manager)
        self.other = User.objects.create_user("other", password="pw")
        self.other.groups.add(Group.objects.get_or_create(name="Team Managers")[0])
        self.admin = User.objects.create_user("la", password="pw")
        self.admin.groups.add(Group.objects.get_or_create(name="League Admin")[0])
        self.page = reverse("payments:payment_page", args=[self.team.pk])

    def test_anonymous_without_session_forbidden(self):
        self.assertEqual(self.client.get(self.page).status_code, 403)

    def test_other_team_manager_forbidden(self):
        # Regression: IDOR - anyone could trigger STK pushes / view any team's payment page.
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.page).status_code, 403)
        p = make_pending(team=self.team)
        self.assertEqual(self.client.get(reverse("payments:payment_status", args=[p.pk])).status_code, 403)

    def test_registering_session_allowed(self):
        s = self.client.session
        s["team_id_for_payment"] = self.team.pk
        s.save()
        self.assertEqual(self.client.get(self.page).status_code, 200)

    def test_manager_and_admin_allowed(self):
        for u in (self.manager, self.admin):
            self.client.force_login(u)
            self.assertEqual(self.client.get(self.page).status_code, 200)

    def test_post_initiates_push_with_normalised_phone(self):
        self.client.force_login(self.manager)
        with mock.patch.object(services, "DarajaClient") as cls:
            cls.return_value.stk_push.return_value = {"CheckoutRequestID": "c1", "MerchantRequestID": "m1"}
            r = self.client.post(self.page, {"phone_number": "0712 345 678"})
        p = Payment.objects.get()
        self.assertRedirects(r, reverse("payments:payment_status", args=[p.pk]), fetch_redirect_response=False)
        self.assertEqual(cls.return_value.stk_push.call_args.kwargs["phone"], "+254712345678")

    def test_invalid_phone_rerenders(self):
        self.client.force_login(self.manager)
        r = self.client.post(self.page, {"phone_number": "12345"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Payment.objects.exists())

    def test_status_page_renders(self):
        # Regression: payments/payment_status.html did not exist (TemplateDoesNotExist).
        self.client.force_login(self.manager)
        p = make_pending(team=self.team)
        with mock.patch.object(services, "_query_result_code", return_value=None):
            r = self.client.get(reverse("payments:payment_status", args=[p.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Waiting for confirmation")
        self.assertNotContains(r, "+254712345678")

    def test_paid_team_redirected(self):
        self.team.payment_status = True
        self.team.save()
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.page).status_code, 302)
