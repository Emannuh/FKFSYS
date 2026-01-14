# Phone Number and County Field Updates

## Summary
Updated the FKF system to enforce Kenya's +254 country code with exactly 9 digits for all phone numbers, and added a dropdown for Kenya's 47 counties.

## Changes Made

### 1. Created Centralized Validators (`fkf_league/validators.py`)
- **`validate_kenya_phone(value)`**: Strict validator requiring +254XXXXXXXXX format
  - Must start with +254
  - Must have exactly 9 digits after +254
  - First digit must be 0, 1, or 7 (Kenyan mobile prefixes)
  - Total length: 13 characters
  
- **`normalize_kenya_phone(value)`**: Converter for flexible input formats
  - Accepts: +254XXXXXXXXX, 254XXXXXXXXX, 0XXXXXXXXX, or XXXXXXXXX
  - Converts all to standard +254XXXXXXXXX format

### 2. Created Constants File (`fkf_league/constants.py`)
- **`KENYA_COUNTIES`**: List of all 47 Kenyan counties for dropdown fields
  - Alphabetically sorted
  - Used in forms as choices for county selection

### 3. Updated Models

#### `teams/models.py`
- **Team.phone_number**
  - Changed `max_length` from 20 to 13
  - Added `validators=[validate_kenya_phone]`
  - Remains `unique=True`
  
- **TeamOfficial.phone_number**
  - Changed `max_length` from 20 to 13
  - Added `validators=[validate_kenya_phone]`

#### `referees/models.py`
- **Referee.phone_number**
  - Changed `max_length` from 20 to 13
  - Added `validators=[validate_kenya_phone]`
  
- **Referee.county**
  - Changed from free text to dropdown
  - Added `choices=KENYA_COUNTIES`
  - `max_length=50`

#### `payments/models.py`
- **Payment.phone_number**
  - Changed `max_length` from 20 to 13
  - Added `validators=[validate_kenya_phone]`

### 4. Updated Forms

All forms now use a **two-field approach** for better UX:

1. **`phone_digits`** (CharField): User-facing field
   - Accepts only 9 digits
   - Pattern: `[0-9]{9}`
   - Placeholder: `712345678`
   - Must start with 0, 1, or 7

2. **`phone_number`** (Model field): Stored in database
   - Automatically created from `phone_digits` in `clean()` method
   - Format: `+254XXXXXXXXX`
   - Saved in `save()` method

#### Forms Updated:
- **`teams/forms.py`** - `TeamRegistrationForm`
  - Removed `phone_number` from Meta.fields
  - Added `phone_digits` CharField
  - Added `clean()` method to validate and create full phone_number
  - Added `save()` method to persist phone_number
  
- **`teams/officials_forms.py`** - `TeamOfficialForm`
  - Removed `phone_number` from Meta.fields
  - Added `phone_digits` CharField
  - Updated `clean()` method for phone validation
  - Added `save()` method
  
- **`referees/forms.py`** - `RefereeRegistrationForm`
  - Removed `phone_number` from Meta.fields
  - Added `phone_digits` CharField (optional)
  - Changed `county` to use Select widget with KENYA_COUNTIES
  - Added `clean()` method
  - Added `save()` method
  
- **`referees/forms.py`** - `RefereeProfileUpdateForm`
  - Added `phone_digits` CharField
  - Changed `county` to use Select widget
  - Added `__init__()` to pre-populate phone_digits from existing phone_number
  - Added `clean()` method
  - Added `save()` method

### 5. Updated Templates

All registration and profile forms now display:
- **"+254" prefix**: Bold, white text on primary blue background
- **9-digit input field**: User only enters 9 digits
- **Help text**: "Enter 9 digits only (e.g., 712345678)"

#### Templates Updated:
1. **`templates/teams/register.html`**
   - Changed from `form.phone_number` to `form.phone_digits`
   - Added input-group with styled "+254" prefix
   - Updated JavaScript validation to use `id_phone_digits`
   - Updated regex to allow first digit: 0, 1, or 7

2. **`templates/referees/register.html`**
   - Changed from `form.phone_number` to `form.phone_digits`
   - Added input-group with styled "+254" prefix
   - County field already uses dropdown (form handles this)

3. **`templates/referees/profile.html`**
   - Changed from `form.phone_number` to `form.phone_digits`
   - Added input-group with styled "+254" prefix

4. **`templates/teams/team_officials.html`**
   - Changed from `form.phone_number` to `form.phone_digits`
   - Added input-group with styled "+254" prefix

### 6. Database Migrations

Migrations created for:
- Phone number field length changes (20 → 13 characters)
- Phone number validator additions
- Referee county field changes (text → choices)

**Status**: Migrations created and applied successfully

## Phone Number Format Examples

### Valid Input (9 digits):
- `712345678` → Stored as `+254712345678`
- `112345678` → Stored as `+254112345678`
- `012345678` → Stored as `+254012345678`

### Invalid Input:
- `812345678` (must start with 0, 1, or 7)
- `71234567` (must be exactly 9 digits)
- `7123456789` (must be exactly 9 digits)
- `+254712345678` (prefix already added, user should not include it)

## Kenya Counties List

The dropdown includes all 47 counties:
Baringo, Bomet, Bungoma, Busia, Elgeyo-Marakwet, Embu, Garissa, Homa Bay, Isiolo, Kajiado, Kakamega, Kericho, Kiambu, Kilifi, Kirinyaga, Kisii, Kisumu, Kitui, Kwale, Laikipia, Lamu, Machakos, Makueni, Mandera, Marsabit, Meru, Migori, Mombasa, Murang'a, Nairobi, Nakuru, Nandi, Narok, Nyamira, Nyandarua, Nyeri, Samburu, Siaya, Taita-Taveta, Tana River, Tharaka-Nithi, Trans-Nzoia, Turkana, Uasin Gishu, Vihiga, Wajir, West Pokot

## Form Validation Flow

1. User enters 9 digits in form (e.g., `712345678`)
2. Form's `clean()` method:
   - Validates exactly 9 digits
   - Validates first digit is 0, 1, or 7
   - Creates full phone number: `+254712345678`
   - Checks for duplicates (if field is unique)
3. Form's `save()` method:
   - Sets `instance.phone_number` from cleaned_data
   - Saves to database

## Testing Checklist

- [x] Team registration form
- [x] Team official addition form
- [x] Referee registration form
- [x] Referee profile update form
- [x] Phone number validation (9 digits)
- [x] Phone number format (+254XXXXXXXXX in DB)
- [x] County dropdown (47 counties)
- [x] Database migrations
- [ ] End-to-end testing with real data
- [ ] M-Pesa payment integration (uses same phone format)

## Notes

1. **Existing Data**: Phone numbers already in the database should be validated against the new format. You may need to run a data migration script to normalize existing phone numbers.

2. **M-Pesa Integration**: The `payments/models.py` Payment model also uses phone_number. Ensure M-Pesa API calls use the +254XXXXXXXXX format.

3. **Display Format**: When displaying phone numbers to users, they see the full +254XXXXXXXXX format. When editing, they see just the 9 digits.

4. **Auto-Account Creation**: The automatic user account creation for approved referees and teams remains functional and unchanged.

## Future Considerations

- Add phone number verification (SMS OTP)
- Support for landline numbers if needed (different format)
- International phone numbers for foreign referees (would need different validator)
