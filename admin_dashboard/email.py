"""Transactional emails for admin-driven account management.

Passwords are never sent by email (PCI DSS 8.3): new and reset accounts get a
single-use "set your password" link built on Django's password-reset tokens,
handled by the stock ``password_reset_confirm`` view.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


def build_password_setup_url(user) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def _send(user, subject: str, template: str, extra_context: dict | None = None) -> bool:
    """Render ``<template>.txt``/``.html`` and send to ``user.email``; True on success."""
    if not user.email:
        logger.warning("Account email not sent: user id=%s has no email address", user.pk)
        return False
    context = {
        'user': user,
        'setup_url': build_password_setup_url(user),
        'login_url': f"{settings.SITE_URL.rstrip('/')}{reverse('login')}",
        **(extra_context or {}),
    }
    try:
        message = EmailMultiAlternatives(
            subject,
            render_to_string(f'{template}.txt', context),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
        message.attach_alternative(render_to_string(f'{template}.html', context), 'text/html')
        message.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Failed to send account email to user id=%s", user.pk)
        return False


def send_account_setup_email(user, role: str | None = None) -> bool:
    """Invite a newly created user to choose their password."""
    return _send(
        user,
        f"Welcome to FKF Meru League Management System{f' — {role}' if role else ''}",
        'admin_dashboard/emails/account_setup',
        {'role': role},
    )


def send_password_reset_email(user) -> bool:
    """Tell a user an admin reset their password and let them choose a new one."""
    return _send(user, 'FKF Meru League — Password Reset', 'admin_dashboard/emails/password_reset')
