# fkf_league/validators.py
"""
Centralized validators for the FKF League System
"""
from django.core.exceptions import ValidationError
import re


def validate_kenya_phone(value):
    """
    Validate Kenya phone number with mandatory +254 country code
    and maximum 9 digits after country code.
    
    Valid format: +254XXXXXXXXX (where X is a digit, first digit must be 7, 1, or 0)
    Examples:
        +254712345678 (valid - 9 digits)
        +254112345678 (valid - 9 digits)
        +254012345678 (valid - 9 digits)
    
    Invalid:
        254712345678 (missing +)
        +2547123456789 (10 digits)
        +254612345678 (doesn't start with 7, 1, or 0)
    """
    if not value:
        raise ValidationError("Phone number is required")
    
    # Remove any whitespace
    value = value.strip()
    
    # Must start with +254
    if not value.startswith('+254'):
        raise ValidationError(
            "Phone number must start with +254 (Kenya country code). "
            "Example: +254712345678"
        )
    
    # Check total length (should be +254 + 9 digits = 13 characters)
    if len(value) != 13:
        raise ValidationError(
            f"Phone number must be exactly 13 characters (+254 followed by 9 digits). "
            f"You entered {len(value)} characters."
        )
    
    # Extract the digits after +254
    digits_after_code = value[4:]
    
    # Check if all characters after +254 are digits
    if not digits_after_code.isdigit():
        raise ValidationError(
            "Phone number must contain only digits after +254"
        )
    
    # Check if it's exactly 9 digits
    if len(digits_after_code) != 9:
        raise ValidationError(
            f"Phone number must have exactly 9 digits after +254. "
            f"You entered {len(digits_after_code)} digits."
        )
    
    # Check if first digit is valid (7, 1, or 0 for Kenyan mobile numbers)
    first_digit = digits_after_code[0]
    if first_digit not in ['7', '1', '0']:
        raise ValidationError(
            f"Invalid phone number. First digit after +254 must be 7, 1, or 0. "
            f"You entered: {first_digit}"
        )
    
    return value


def normalize_kenya_phone(phone):
    """
    Normalize phone number to +254XXXXXXXXX format
    
    Handles these input formats:
    - 712345678 (9 digits starting with 7)
    - 0712345678 (10 digits starting with 07)
    - 254712345678 (12 digits starting with 254)
    - +254712345678 (already correct)
    
    Returns: +254XXXXXXXXX or raises ValidationError
    """
    if not phone:
        raise ValidationError("Phone number is required")
    
    # Remove all spaces, dashes, and parentheses
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Remove any non-digit characters except leading +
    if phone.startswith('+'):
        phone = '+' + ''.join(filter(str.isdigit, phone[1:]))
    else:
        phone = ''.join(filter(str.isdigit, phone))
    
    # Convert different formats to +254XXXXXXXXX
    if phone.startswith('+254'):
        # Already has +254, validate length
        if len(phone) != 13:
            raise ValidationError(
                f"Invalid phone number length. Expected +254 followed by 9 digits. "
                f"Got {len(phone)} characters total."
            )
        normalized = phone
        
    elif phone.startswith('254'):
        # Has 254 but missing +
        if len(phone) != 12:
            raise ValidationError(
                f"Invalid phone number length. Expected 254 followed by 9 digits. "
                f"Got {len(phone)} characters total."
            )
        normalized = '+' + phone
        
    elif phone.startswith('0'):
        # Starts with 0 (e.g., 0712345678)
        if len(phone) != 10:
            raise ValidationError(
                f"Invalid phone number length. Expected 0 followed by 9 digits. "
                f"Got {len(phone)} characters total."
            )
        # Remove leading 0 and add +254
        normalized = '+254' + phone[1:]
        
    elif phone.startswith('7') or phone.startswith('1'):
        # Just 9 digits starting with 7 or 1
        if len(phone) != 9:
            raise ValidationError(
                f"Invalid phone number length. Expected 9 digits. "
                f"Got {len(phone)} digits."
            )
        normalized = '+254' + phone
        
    else:
        raise ValidationError(
            "Invalid phone number format. Must start with +254, 254, 0, 7, or 1. "
            f"Examples: +254712345678, 0712345678, 712345678"
        )
    
    # Final validation using the strict validator
    validate_kenya_phone(normalized)
    
    return normalized
