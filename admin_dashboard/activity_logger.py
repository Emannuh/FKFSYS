"""The single entry point for writing the audit trail.

Everything that records an ``ActivityLog`` row goes through :func:`log_activity`:
explicit calls from views, the request middleware and the auth signal handlers.

Guarantees:
* logging never raises into the caller — failures are reported through the
  ``admin_dashboard.audit`` logger (without request data) and swallowed;
* ``extra_data`` is scrubbed: keys that look like secrets or personal data are
  masked before storage;
* a request that was explicitly audit-logged is marked so the middleware does
  not record a duplicate generic entry.
"""
from __future__ import annotations

import ipaddress
import logging
from typing import Any

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction

from .models import ActivityLog

logger = logging.getLogger('admin_dashboard.audit')

Action = ActivityLog.Action

#: Request attribute set once a request has an explicit audit entry.
REQUEST_LOGGED_ATTR = '_audit_logged'

MASK = '***'
_SENSITIVE_KEY_PARTS = (
    'password', 'passwd', 'secret', 'token', 'csrf', 'key', 'pin', 'otp',
    'card', 'cvv', 'cvc', 'pan', 'account', 'phone', 'msisdn', 'mobile',
    'email', 'id_number', 'national_id', 'passport', 'dob', 'birth', 'address',
)


def _is_sensitive_key(key: str) -> bool:
    k = str(key).lower()
    return any(part in k for part in _SENSITIVE_KEY_PARTS)


def scrub(data: Any) -> Any:
    """Recursively mask values stored under secret/PII-looking keys."""
    if isinstance(data, dict):
        return {k: (MASK if _is_sensitive_key(k) else scrub(v)) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [scrub(v) for v in data]
    if isinstance(data, (str, int, float, bool)) or data is None:
        return data
    return str(data)


def _trust_forwarded_for() -> bool:
    """Trust X-Forwarded-For only when deployed behind a TLS-terminating proxy."""
    return getattr(
        settings, 'AUDIT_TRUST_X_FORWARDED_FOR',
        bool(getattr(settings, 'SECURE_PROXY_SSL_HEADER', None)),
    )


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def get_client_ip(request) -> str | None:
    """Best-effort client IP; ignores spoofable headers unless behind a proxy."""
    if _trust_forwarded_for():
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip = _valid_ip(forwarded.split(',')[0]) if forwarded else None
        if ip:
            return ip
    return _valid_ip(request.META.get('REMOTE_ADDR'))


def log_activity(
    user,
    action: str,
    description: str,
    *,
    obj: models.Model | None = None,
    request=None,
    extra_data: dict | None = None,
) -> ActivityLog | None:
    """Append one audit row. Never raises; returns ``None`` on failure."""
    try:
        if user is not None and not getattr(user, 'is_authenticated', False):
            user = None
        entry = ActivityLog(
            user=user,
            action=action,
            description=description[:2000],
            extra_data=scrub(extra_data or {}),
        )
        if obj is not None and obj.pk is not None:
            entry.content_type = ContentType.objects.get_for_model(obj)
            entry.object_id = obj.pk
            entry.object_repr = str(obj)[:200]
        if request is not None:
            entry.ip_address = get_client_ip(request)
            entry.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            setattr(request, REQUEST_LOGGED_ATTR, True)
        with transaction.atomic():  # savepoint: a failed insert can't poison the caller's transaction
            entry.save()
        return entry
    except Exception:  # audit logging must never break the request
        logger.exception("Failed to write audit log entry (action=%s)", action)
        return None
