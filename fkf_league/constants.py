"""
fkf_league/constants.py

Shared constants and named status values.
Use these instead of raw strings throughout the codebase.
"""
from __future__ import annotations


class MatchStatus:
    SCHEDULED  = 'scheduled'
    LIVE       = 'live'
    ONGOING    = 'ongoing'
    COMPLETED  = 'completed'
    POSTPONED  = 'postponed'
    CANCELLED  = 'cancelled'

    ACTIVE_STATUSES   = (SCHEDULED, ONGOING)
    INACTIVE_STATUSES = (COMPLETED, POSTPONED, CANCELLED)


class TeamStatus:
    PENDING   = 'pending'
    APPROVED  = 'approved'
    REJECTED  = 'rejected'
    SUSPENDED = 'suspended'


class TransferStatus:
    PENDING_PARENT = 'pending_parent'
    APPROVED       = 'approved'
    REJECTED       = 'rejected'
    CANCELLED      = 'cancelled'


class ReportStatus:
    DRAFT     = 'draft'
    SUBMITTED = 'submitted'
    APPROVED  = 'approved'
    REJECTED  = 'rejected'


# Kenya's 47 Counties (alphabetically ordered)
KENYA_COUNTIES: list[tuple[str, str]] = [
    ('baringo', 'Baringo'),
    ('bomet', 'Bomet'),
    ('bungoma', 'Bungoma'),
    ('busia', 'Busia'),
    ('elgeyo_marakwet', 'Elgeyo Marakwet'),
    ('embu', 'Embu'),
    ('garissa', 'Garissa'),
    ('homa_bay', 'Homa Bay'),
    ('isiolo', 'Isiolo'),
    ('kajiado', 'Kajiado'),
    ('kakamega', 'Kakamega'),
    ('kericho', 'Kericho'),
    ('kiambu', 'Kiambu'),
    ('kilifi', 'Kilifi'),
    ('kirinyaga', 'Kirinyaga'),
    ('kisii', 'Kisii'),
    ('kisumu', 'Kisumu'),
    ('kitui', 'Kitui'),
    ('kwale', 'Kwale'),
    ('laikipia', 'Laikipia'),
    ('lamu', 'Lamu'),
    ('machakos', 'Machakos'),
    ('makueni', 'Makueni'),
    ('mandera', 'Mandera'),
    ('marsabit', 'Marsabit'),
    ('meru', 'Meru'),
    ('migori', 'Migori'),
    ('mombasa', 'Mombasa'),
    ('muranga', "Murang'a"),
    ('nairobi', 'Nairobi'),
    ('nakuru', 'Nakuru'),
    ('nandi', 'Nandi'),
    ('narok', 'Narok'),
    ('nyamira', 'Nyamira'),
    ('nyandarua', 'Nyandarua'),
    ('nyeri', 'Nyeri'),
    ('samburu', 'Samburu'),
    ('siaya', 'Siaya'),
    ('taita_taveta', 'Taita Taveta'),
    ('tana_river', 'Tana River'),
    ('tharaka_nithi', 'Tharaka Nithi'),
    ('trans_nzoia', 'Trans Nzoia'),
    ('turkana', 'Turkana'),
    ('uasin_gishu', 'Uasin Gishu'),
    ('vihiga', 'Vihiga'),
    ('wajir', 'Wajir'),
    ('west_pokot', 'West Pokot'),
]
