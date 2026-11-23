"""
External player-verification integrations.

- Kenya IPRS (Integrated Population Registration System) — national ID lookup
- FIFA Connect — sanctions / transfer-ban lookup

Both are disabled unless explicitly enabled through environment variables:
``IPRS_ENABLED``, ``IPRS_API_KEY``, ``IPRS_API_SECRET``, ``IPRS_BASE_URL``;
``FIFA_CONNECT_ENABLED``, ``FIFA_CONNECT_API_KEY``, ``FIFA_ASSOCIATION_CODE``,
``FIFA_CONNECT_URL``.

Data-protection rules (PCI/SOC2):
- identity data (ID numbers, names, DOB) and credentials are never logged;
- registry data is never echoed back to the user in error messages;
- cache keys are hashed so raw ID numbers are not stored as keys;
- every outbound request has a connect/read timeout and failures degrade to
  ``verified=False`` instead of raising.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from difflib import SequenceMatcher
from typing import Any

import requests
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# (connect, read) seconds
REQUEST_TIMEOUT = (5, 15)

VerificationResult = dict[str, Any]


def _result(*, valid: bool, verified: bool, data: dict | None = None, errors=None) -> VerificationResult:
    return {'valid': valid, 'verified': verified, 'data': data, 'errors': list(errors or [])}


def _env_flag(name: str) -> bool:
    return os.environ.get(name, 'False').strip().lower() in {'1', 'true', 'yes'}


def _hashed_key(prefix: str, *parts) -> str:
    digest = hashlib.sha256('|'.join(str(p).strip().lower() for p in parts).encode()).hexdigest()
    return f'{prefix}_{digest}'


class IPRSError(Exception):
    """Raised internally when the IPRS service cannot be used."""


class IPRSVerification:
    """Verify Kenyan national IDs against IPRS."""

    CACHE_SECONDS = 60 * 60 * 24 * 30

    def __init__(self):
        self.api_key = os.environ.get('IPRS_API_KEY')
        self.api_secret = os.environ.get('IPRS_API_SECRET')
        self.base_url = os.environ.get('IPRS_BASE_URL', 'https://iprs.go.ke/api/v1').rstrip('/')
        self.enabled = _env_flag('IPRS_ENABLED')

    def verify_id_number(self, id_number, full_name=None, date_of_birth=None) -> VerificationResult:
        """
        Returns ``{'valid', 'verified', 'data', 'errors'}``.
        ``verified`` is False whenever IPRS could not give an authoritative answer.
        """
        if not self.enabled or not self.api_key:
            return _result(valid=True, verified=False, errors=['IPRS verification not configured'])

        cache_key = _hashed_key('iprs_verify', id_number, full_name or '', date_of_birth or '')
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            response = requests.post(
                f'{self.base_url}/verify/id',
                json={'id_number': id_number, 'request_id': self._generate_request_id()},
                headers={
                    'Authorization': f'Bearer {self._get_access_token()}',
                    'Content-Type': 'application/json',
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.Timeout:
            logger.warning("IPRS verification timed out")
            return _result(valid=False, verified=False, errors=['IPRS verification timeout - please try again'])
        except (requests.RequestException, IPRSError) as exc:
            logger.warning("IPRS verification unavailable (%s)", type(exc).__name__)
            return _result(valid=False, verified=False, errors=['IPRS verification is temporarily unavailable'])

        if response.status_code == 404:
            return _result(valid=False, verified=True, errors=['ID number not found in IPRS database'])
        if response.status_code != 200:
            logger.warning("IPRS verification failed with HTTP %s", response.status_code)
            return _result(valid=False, verified=False, errors=[f'IPRS API error: {response.status_code}'])

        try:
            payload = response.json()
        except ValueError:
            logger.warning("IPRS returned a non-JSON response")
            return _result(valid=False, verified=False, errors=['IPRS verification is temporarily unavailable'])

        result = _result(valid=payload.get('status') == 'valid', verified=True)
        iprs_name = payload.get('full_name')
        iprs_dob = payload.get('date_of_birth')
        # Never echo registry values back to the caller — only say which field mismatched.
        if full_name and iprs_name and not self._names_match(full_name, iprs_name):
            result['valid'] = False
            result['errors'].append('Name does not match the IPRS record for this ID number')
        if date_of_birth and iprs_dob and str(date_of_birth) != str(iprs_dob):
            result['valid'] = False
            result['errors'].append('Date of birth does not match the IPRS record for this ID number')

        cache.set(cache_key, result, self.CACHE_SECONDS)
        return result

    def _get_access_token(self) -> str:
        token = cache.get('iprs_access_token')
        if token:
            return token
        try:
            response = requests.post(
                f'{self.base_url}/oauth/token',
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.api_key,
                    'client_secret': self.api_secret,
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise IPRSError('token request failed') from exc
        if response.status_code != 200:
            raise IPRSError(f'token request returned HTTP {response.status_code}')
        try:
            data = response.json()
            token = data['access_token']
        except (ValueError, KeyError) as exc:
            raise IPRSError('malformed token response') from exc
        expires_in = int(data.get('expires_in', 3600))
        cache.set('iprs_access_token', token, max(expires_in - 300, 60))
        return token

    @staticmethod
    def _generate_request_id() -> str:
        return f"FKF-{timezone.now():%Y%m%d%H%M%S}-{secrets.token_hex(4)}"

    @staticmethod
    def _names_match(name1: str, name2: str, threshold: float = 0.8) -> bool:
        a = ' '.join(name1.lower().split())
        b = ' '.join(name2.lower().split())
        return SequenceMatcher(None, a, b).ratio() >= threshold


class FIFAConnectVerification:
    """Check a player against FIFA Connect (sanctions / transfer bans)."""

    CACHE_SECONDS = 60 * 60 * 24 * 7

    def __init__(self):
        self.api_key = os.environ.get('FIFA_CONNECT_API_KEY')
        self.association_code = os.environ.get('FIFA_ASSOCIATION_CODE', 'KEN')
        self.base_url = os.environ.get('FIFA_CONNECT_URL', 'https://connect.fifa.com/api/v1').rstrip('/')
        self.enabled = _env_flag('FIFA_CONNECT_ENABLED')

    def verify_player(self, player_data: dict) -> VerificationResult:
        if not self.enabled or not self.api_key:
            return _result(valid=True, verified=False, errors=['FIFA Connect not configured'])

        cache_key = _hashed_key(
            'fifa_verify', player_data['first_name'], player_data['last_name'], player_data['date_of_birth']
        )
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            response = requests.post(
                f'{self.base_url}/players/search',
                json={
                    'first_name': player_data['first_name'],
                    'last_name': player_data['last_name'],
                    'date_of_birth': str(player_data['date_of_birth']),
                    'nationality': player_data.get('nationality') or 'KEN',
                },
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'X-Association-Code': self.association_code,
                    'Content-Type': 'application/json',
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning("FIFA Connect verification unavailable (%s)", type(exc).__name__)
            return _result(valid=False, verified=False, errors=['FIFA Connect is temporarily unavailable'])

        if response.status_code == 404:
            # Not registered with FIFA — normal for local players.
            return _result(valid=True, verified=True, errors=['Player not registered in FIFA Connect (local player)'])
        if response.status_code != 200:
            logger.warning("FIFA Connect verification failed with HTTP %s", response.status_code)
            return _result(valid=False, verified=False, errors=[f'FIFA Connect error: {response.status_code}'])

        try:
            data = response.json()
        except ValueError:
            logger.warning("FIFA Connect returned a non-JSON response")
            return _result(valid=False, verified=False, errors=['FIFA Connect is temporarily unavailable'])

        result = _result(valid=True, verified=True, data={'fifa_id': data.get('player_id')})
        sanctions = data.get('sanctions') or []
        if sanctions:
            result['valid'] = False
            result['errors'].append(f"Player has FIFA sanctions: {', '.join(map(str, sanctions))}")
        if data.get('transfer_ban'):
            result['valid'] = False
            result['errors'].append('Player is under FIFA transfer ban')

        cache.set(cache_key, result, self.CACHE_SECONDS)
        return result
