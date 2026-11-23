"""
fkf_league/validators.py

Centralised validators for the FKF League system.

``validate_kenya_phone`` is referenced by model fields and migrations
(teams, referees, payments) — keep its import path and name stable.
``normalize_kenya_phone`` is used by form ``clean_*`` methods (and M-Pesa code)
to accept common local formats and return the canonical ``+254XXXXXXXXX``.
"""
from __future__ import annotations

import re

from django.core.exceptions import ValidationError

KENYA_PREFIX = '+254'
_LOCAL_DIGITS = 9
_VALID_FIRST_DIGITS = frozenset('710')
_SEPARATORS = re.compile(r'[\s\-()]')


def validate_kenya_phone(value: str | None) -> str:
    """
    Validate a Kenyan phone number in strict ``+254XXXXXXXXX`` form.

    Exactly nine digits must follow ``+254`` and the first of them must be 7, 1 or 0.
    Returns the stripped value; raises ``ValidationError`` otherwise.
    """
    if not value:
        raise ValidationError('Phone number is required')

    value = value.strip()
    if not value.startswith(KENYA_PREFIX):
        raise ValidationError(
            'Phone number must start with +254 (Kenya country code). Example: +254712345678'
        )
    if len(value) != len(KENYA_PREFIX) + _LOCAL_DIGITS:
        raise ValidationError(
            'Phone number must be exactly 13 characters (+254 followed by 9 digits). '
            f'You entered {len(value)} characters.'
        )
    local = value[len(KENYA_PREFIX):]
    if not local.isascii() or not local.isdigit():
        raise ValidationError('Phone number must contain only digits after +254')
    if local[0] not in _VALID_FIRST_DIGITS:
        raise ValidationError(
            'Invalid phone number. First digit after +254 must be 7, 1, or 0. '
            f'You entered: {local[0]}'
        )
    return value


def normalize_kenya_phone(phone: str | None) -> str:
    """
    Normalise a Kenyan phone number to ``+254XXXXXXXXX``.

    Accepts ``712345678``, ``0712345678``, ``254712345678`` and ``+254712345678``
    (spaces, dashes and parentheses are ignored). Raises ``ValidationError`` if the
    result is not a valid number per :func:`validate_kenya_phone`.
    """
    if not phone:
        raise ValidationError('Phone number is required')

    phone = _SEPARATORS.sub('', phone)
    has_plus = phone.startswith('+')
    digits = ''.join(ch for ch in phone if ch.isascii() and ch.isdigit())
    if has_plus:
        phone = '+' + digits
    else:
        phone = digits

    if phone.startswith(KENYA_PREFIX):
        expected, normalized = 13, phone
        hint = '+254 followed by 9 digits'
    elif phone.startswith('254'):
        expected, normalized = 12, '+' + phone
        hint = '254 followed by 9 digits'
    elif phone.startswith('0'):
        expected, normalized = 10, KENYA_PREFIX + phone[1:]
        hint = '0 followed by 9 digits'
    elif phone[:1] in ('7', '1'):
        expected, normalized = 9, KENYA_PREFIX + phone
        hint = '9 digits'
    else:
        raise ValidationError(
            'Invalid phone number format. Must start with +254, 254, 0, 7, or 1. '
            'Examples: +254712345678, 0712345678, 712345678'
        )

    if len(phone) != expected:
        raise ValidationError(
            f'Invalid phone number length. Expected {hint}. Got {len(phone)} characters total.'
        )

    return validate_kenya_phone(normalized)
