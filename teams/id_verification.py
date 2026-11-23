"""
Player identity checks used during registration: ID-number format, age
eligibility and league-wide duplicate detection.

Error messages deliberately never reveal another player's identity (name,
team or ID number) — they are shown to team managers.
"""
from __future__ import annotations

import re
from datetime import date

from django.core.exceptions import ValidationError
from django.utils import timezone

_OLD_ID = re.compile(r'^\d{8}$')
_NEW_ID = re.compile(r'^[A-Z0-9]{7,12}$')


def age_on(date_of_birth: date, today: date | None = None) -> int:
    today = today or timezone.localdate()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


class IDVerification:
    """Kenya National ID / passport number checks."""

    @staticmethod
    def validate_kenyan_id(id_number) -> str:
        """Normalise and validate the ID format (8 digits, or 7-12 alphanumerics)."""
        if not id_number:
            raise ValidationError("ID number is required")
        id_number = str(id_number).replace(' ', '').strip().upper()
        if not (_OLD_ID.match(id_number) or _NEW_ID.match(id_number)):
            raise ValidationError(
                "Invalid ID number format. Must be 8 digits (e.g., 12345678) "
                "or new format with 7-12 characters (e.g., 12345678A)"
            )
        return id_number

    @staticmethod
    def check_age_eligibility(date_of_birth: date, min_age: int = 16, max_age: int = 45) -> int:
        if not date_of_birth:
            raise ValidationError("Date of birth is required")
        age = age_on(date_of_birth)
        if age < min_age:
            raise ValidationError(f"Player must be at least {min_age} years old. Current age: {age}")
        if age > max_age:
            raise ValidationError(f"Player cannot be older than {max_age} years. Current age: {age}")
        return age


class DuplicatePlayerChecker:
    """League-wide duplicate registration checks."""

    @staticmethod
    def check_id_number(id_number: str, exclude_player_id: int | None = None) -> None:
        from teams.models import Player

        qs = Player.objects.filter(id_number=id_number)
        if exclude_player_id:
            qs = qs.exclude(pk=exclude_player_id)
        if qs.exists():
            raise ValidationError("A player with this ID number is already registered in the league.")

    @staticmethod
    def check_duplicate_by_name_dob(
        first_name: str, last_name: str, date_of_birth: date, exclude_player_id: int | None = None
    ) -> None:
        from teams.models import Player

        qs = Player.objects.filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name,
            date_of_birth=date_of_birth,
        )
        if exclude_player_id:
            qs = qs.exclude(pk=exclude_player_id)
        if qs.exists():
            raise ValidationError(
                "A player with the same name and date of birth is already registered in the league."
            )
