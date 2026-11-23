"""
Safaricom M-Pesa Daraja client (STK push + STK status query).

This is the single Daraja integration in the project. Configuration comes from
``settings.MPESA_CONFIG`` (populated from the environment); nothing here reads
``os.environ`` directly.

Security notes (PCI/SOC2):
- Credentials, the passkey, the generated STK password and access tokens are
  never logged. Request payloads are never logged.
- Phone numbers are masked in logs (see :func:`mask_phone`).
- Every HTTP call has a timeout; failures raise :class:`DarajaError`.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac

logger = logging.getLogger(__name__)

BASE_URLS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}
HTTP_TIMEOUT = (5, 30)  # (connect, read) seconds
_NAIROBI = ZoneInfo("Africa/Nairobi")


class DarajaError(Exception):
    """Daraja call failed (network, HTTP error, or unexpected response)."""


class DarajaConfigError(DarajaError):
    """M-Pesa settings are missing or invalid."""


def mask_phone(phone: str | int | None) -> str:
    """Return a log-safe phone number, e.g. ``2547******78``."""
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) < 6:
        return "***"
    return f"{digits[:4]}{'*' * (len(digits) - 6)}{digits[-2:]}"


def callback_token() -> str:
    """
    Unguessable, stable token embedded in the callback URL path.

    Derived from SECRET_KEY, so it is never stored or configured separately.
    Rotating SECRET_KEY invalidates callbacks for STK pushes still in flight
    (those payments are then settled by the status query instead).
    """
    return salted_hmac("payments.mpesa.callback", "stk-callback", algorithm="sha256").hexdigest()


class DarajaClient:
    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config if config is not None else getattr(settings, "MPESA_CONFIG", {})
        self.consumer_key = cfg.get("CONSUMER_KEY") or ""
        self.consumer_secret = cfg.get("CONSUMER_SECRET") or ""
        self.shortcode = str(cfg.get("SHORTCODE") or "")
        self.passkey = cfg.get("PASSKEY") or ""
        self.callback_base = cfg.get("CALLBACK_URL") or ""
        self.environment = (cfg.get("ENVIRONMENT") or "sandbox").strip().lower()

        if self.environment not in BASE_URLS:
            raise DarajaConfigError("MPESA_ENVIRONMENT must be 'sandbox' or 'production'")
        missing = [
            name for name, value in (
                ("MPESA_CONSUMER_KEY", self.consumer_key),
                ("MPESA_CONSUMER_SECRET", self.consumer_secret),
                ("MPESA_SHORTCODE", self.shortcode),
                ("MPESA_PASSKEY", self.passkey),
            ) if not value
        ]
        if missing:
            raise DarajaConfigError(f"M-Pesa not configured: missing {', '.join(missing)}")
        self.base_url = BASE_URLS[self.environment]

    # ── helpers ─────────────────────────────────────────────────────────
    @property
    def _token_cache_key(self) -> str:
        key_id = hashlib.sha256(self.consumer_key.encode()).hexdigest()[:16]
        return f"payments:mpesa:token:{self.environment}:{key_id}"

    def _password(self) -> tuple[str, str]:
        timestamp = timezone.now().astimezone(_NAIROBI).strftime("%Y%m%d%H%M%S")
        raw = f"{self.shortcode}{self.passkey}{timestamp}".encode()
        return base64.b64encode(raw).decode(), timestamp

    def callback_url(self) -> str:
        """
        Absolute callback URL including the secret token.

        Only the scheme+host of MPESA_CALLBACK_URL (or SITE_URL) is used; the
        path always comes from the ``payments:payment_callback`` route.
        """
        base = self.callback_base or getattr(settings, "SITE_URL", "")
        parts = urlsplit(base)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise DarajaConfigError("MPESA_CALLBACK_URL (or SITE_URL) must be an absolute URL")
        if self.environment == "production" and parts.scheme != "https":
            raise DarajaConfigError("MPESA_CALLBACK_URL must use https in production")
        path = reverse("payments:payment_callback", kwargs={"token": callback_token()})
        return f"{parts.scheme}://{parts.netloc}{path}"

    def _post(self, path: str, payload: dict[str, Any], what: str) -> dict[str, Any]:
        token = self.get_access_token()
        try:
            response = requests.post(
                f"{self.base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.error("M-Pesa %s: network error (%s)", what, type(exc).__name__)
            raise DarajaError(f"{what}: network error") from exc

        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if response.status_code != 200:
            # errorCode is Safaricom's own field - no secrets in it.
            logger.warning(
                "M-Pesa %s: HTTP %s errorCode=%s",
                what, response.status_code, data.get("errorCode", "-"),
            )
            raise DarajaError(f"{what} failed (HTTP {response.status_code})")
        return data

    # ── API ─────────────────────────────────────────────────────────────
    def get_access_token(self) -> str:
        """OAuth token, cached until shortly before it expires."""
        cached = cache.get(self._token_cache_key)
        if cached:
            return cached
        try:
            response = requests.get(
                f"{self.base_url}/oauth/v1/generate",
                params={"grant_type": "client_credentials"},
                auth=(self.consumer_key, self.consumer_secret),
                timeout=HTTP_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            token = data["access_token"]
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            logger.error("M-Pesa: access token request failed (%s)", type(exc).__name__)
            raise DarajaError("Could not authenticate with M-Pesa") from exc

        try:
            expires_in = int(data.get("expires_in", 3599))
        except (TypeError, ValueError):
            expires_in = 3599
        cache.set(self._token_cache_key, token, max(expires_in - 60, 60))
        return token

    def stk_push(self, phone: str, amount: int, account_reference: str, description: str) -> dict[str, Any]:
        """
        Send an STK push. ``phone`` is E.164 (+2547XXXXXXXX) as produced by
        ``fkf_league.validators.normalize_kenya_phone``.
        Returns Safaricom's response (contains CheckoutRequestID/MerchantRequestID).
        """
        msisdn = phone.lstrip("+")
        password, timestamp = self._password()
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": msisdn,
            "PartyB": self.shortcode,
            "PhoneNumber": msisdn,
            "CallBackURL": self.callback_url(),
            "AccountReference": str(account_reference)[:12],
            "TransactionDesc": str(description)[:13],
        }
        logger.info("M-Pesa STK push requested: phone=%s amount=%s", mask_phone(msisdn), int(amount))
        data = self._post("/mpesa/stkpush/v1/processrequest", payload, "STK push")
        if str(data.get("ResponseCode")) != "0" or not data.get("CheckoutRequestID"):
            logger.warning("M-Pesa STK push rejected: ResponseCode=%s", data.get("ResponseCode"))
            raise DarajaError("STK push was not accepted")
        return data

    def query_status(self, checkout_request_id: str) -> dict[str, Any]:
        """Ask Daraja for the authoritative result of an STK push."""
        password, timestamp = self._password()
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }
        return self._post("/mpesa/stkpushquery/v1/query", payload, "STK query")
