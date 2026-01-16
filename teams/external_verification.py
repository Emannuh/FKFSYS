"""
External API Integrations for Player Verification
- Kenya IPRS (Integrated Population Registration System) for ID verification
- FIFA Connect for international player verification
"""

import requests
import hashlib
import json
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()


class IPRSVerification:
    """
    Integration with Kenya's IPRS (Integrated Population Registration System)
    For verifying National ID cards
    """
    
    def __init__(self):
        # IPRS API credentials (get from eCitizen/IPRS portal)
        self.api_key = os.getenv('IPRS_API_KEY')
        self.api_secret = os.getenv('IPRS_API_SECRET')
        self.base_url = os.getenv('IPRS_BASE_URL', 'https://iprs.go.ke/api/v1')
        self.enabled = os.getenv('IPRS_ENABLED', 'False').lower() == 'true'
    
    def verify_id_number(self, id_number, full_name=None, date_of_birth=None):
        """
        Verify Kenya National ID with IPRS
        
        Args:
            id_number: Kenya National ID number
            full_name: Expected full name (optional, for matching)
            date_of_birth: Expected DOB (optional, for matching)
        
        Returns:
            dict: {
                'valid': bool,
                'verified': bool,
                'data': dict or None,
                'errors': list
            }
        """
        # Check if IPRS is enabled
        if not self.enabled or not self.api_key:
            return {
                'valid': True,  # Skip verification if not configured
                'verified': False,
                'data': None,
                'errors': ['IPRS verification not configured']
            }
        
        # Check cache first (valid for 30 days)
        cache_key = f'iprs_verify_{id_number}'
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Prepare request
            url = f"{self.base_url}/verify/id"
            headers = {
                'Authorization': f'Bearer {self._get_access_token()}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'id_number': id_number,
                'request_id': self._generate_request_id()
            }
            
            # Make API request
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                result = {
                    'valid': data.get('status') == 'valid',
                    'verified': True,
                    'data': {
                        'id_number': data.get('id_number'),
                        'full_name': data.get('full_name'),
                        'date_of_birth': data.get('date_of_birth'),
                        'gender': data.get('gender'),
                        'photo': data.get('photo_url'),  # Optional
                        'citizenship': data.get('citizenship', 'Kenyan'),
                    },
                    'errors': []
                }
                
                # Validate name match if provided
                if full_name and result['data']['full_name']:
                    if not self._names_match(full_name, result['data']['full_name']):
                        result['valid'] = False
                        result['errors'].append(
                            f"Name mismatch: Provided '{full_name}' vs "
                            f"IPRS '{result['data']['full_name']}'"
                        )
                
                # Validate DOB match if provided
                if date_of_birth and result['data']['date_of_birth']:
                    if str(date_of_birth) != result['data']['date_of_birth']:
                        result['valid'] = False
                        result['errors'].append(
                            f"Date of birth mismatch: Provided '{date_of_birth}' vs "
                            f"IPRS '{result['data']['date_of_birth']}'"
                        )
                
                # Cache result for 30 days
                cache.set(cache_key, result, 60 * 60 * 24 * 30)
                
                return result
            
            elif response.status_code == 404:
                return {
                    'valid': False,
                    'verified': True,
                    'data': None,
                    'errors': ['ID number not found in IPRS database - possible fake ID']
                }
            
            else:
                return {
                    'valid': False,
                    'verified': False,
                    'data': None,
                    'errors': [f'IPRS API error: {response.status_code}']
                }
        
        except requests.exceptions.Timeout:
            return {
                'valid': False,
                'verified': False,
                'data': None,
                'errors': ['IPRS verification timeout - please try again']
            }
        
        except Exception as e:
            return {
                'valid': False,
                'verified': False,
                'data': None,
                'errors': [f'IPRS verification error: {str(e)}']
            }
    
    def _get_access_token(self):
        """Get or refresh IPRS access token"""
        cache_key = 'iprs_access_token'
        token = cache.get(cache_key)
        
        if token:
            return token
        
        # Request new token
        url = f"{self.base_url}/oauth/token"
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.api_key,
            'client_secret': self.api_secret
        }
        
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            token = data['access_token']
            expires_in = data.get('expires_in', 3600)
            
            # Cache token
            cache.set(cache_key, token, expires_in - 300)  # Refresh 5 min early
            return token
        
        raise Exception('Failed to get IPRS access token')
    
    def _generate_request_id(self):
        """Generate unique request ID"""
        return f"FKF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(4).hex()}"
    
    def _names_match(self, name1, name2, threshold=0.8):
        """Check if two names match (fuzzy matching)"""
        from difflib import SequenceMatcher
        
        # Normalize names
        name1 = ' '.join(name1.lower().split())
        name2 = ' '.join(name2.lower().split())
        
        # Calculate similarity
        similarity = SequenceMatcher(None, name1, name2).ratio()
        
        return similarity >= threshold


class FIFAConnectVerification:
    """
    Integration with FIFA Connect (FIFA's player registration system)
    Requires official FKF credentials and FIFA API access
    """
    
    def __init__(self):
        # FIFA Connect credentials (requires FKF official access)
        self.api_key = os.getenv('FIFA_CONNECT_API_KEY')
        self.association_code = os.getenv('FIFA_ASSOCIATION_CODE', 'KEN')  # Kenya
        self.base_url = os.getenv('FIFA_CONNECT_URL', 'https://connect.fifa.com/api/v1')
        self.enabled = os.getenv('FIFA_CONNECT_ENABLED', 'False').lower() == 'true'
    
    def verify_player(self, player_data):
        """
        Verify player with FIFA Connect
        
        Args:
            player_data: dict with:
                - first_name
                - last_name
                - date_of_birth
                - nationality
                - id_number (optional)
                - fkf_license_number (optional)
        
        Returns:
            dict: verification result
        """
        if not self.enabled or not self.api_key:
            return {
                'valid': True,  # Skip if not configured
                'verified': False,
                'data': None,
                'errors': ['FIFA Connect not configured']
            }
        
        # Check cache
        cache_key = self._generate_cache_key(player_data)
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            url = f"{self.base_url}/players/search"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'X-Association-Code': self.association_code,
                'Content-Type': 'application/json'
            }
            
            payload = {
                'first_name': player_data['first_name'],
                'last_name': player_data['last_name'],
                'date_of_birth': str(player_data['date_of_birth']),
                'nationality': player_data.get('nationality', 'KEN')
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                result = {
                    'valid': True,
                    'verified': True,
                    'data': {
                        'fifa_id': data.get('player_id'),
                        'full_name': data.get('full_name'),
                        'date_of_birth': data.get('date_of_birth'),
                        'nationality': data.get('nationality'),
                        'current_club': data.get('current_club'),
                        'registration_status': data.get('status'),
                        'sanctions': data.get('sanctions', []),
                        'transfer_ban': data.get('transfer_ban', False),
                    },
                    'errors': []
                }
                
                # Check for sanctions
                if result['data']['sanctions']:
                    result['valid'] = False
                    result['errors'].append(
                        f"Player has FIFA sanctions: {', '.join(result['data']['sanctions'])}"
                    )
                
                # Check transfer ban
                if result['data']['transfer_ban']:
                    result['valid'] = False
                    result['errors'].append("Player is under FIFA transfer ban")
                
                # Cache for 7 days
                cache.set(cache_key, result, 60 * 60 * 24 * 7)
                
                return result
            
            elif response.status_code == 404:
                # Player not found in FIFA database (okay for local players)
                return {
                    'valid': True,
                    'verified': True,
                    'data': None,
                    'errors': ['Player not registered in FIFA Connect (local player)']
                }
            
            else:
                return {
                    'valid': False,
                    'verified': False,
                    'data': None,
                    'errors': [f'FIFA Connect error: {response.status_code}']
                }
        
        except Exception as e:
            return {
                'valid': False,
                'verified': False,
                'data': None,
                'errors': [f'FIFA Connect error: {str(e)}']
            }
    
    def _generate_cache_key(self, player_data):
        """Generate cache key from player data"""
        key_string = f"{player_data['first_name']}{player_data['last_name']}{player_data['date_of_birth']}"
        return f"fifa_verify_{hashlib.md5(key_string.encode()).hexdigest()}"


class VerificationOrchestrator:
    """
    Orchestrates verification from multiple sources
    Combines IPRS and FIFA Connect verification
    """
    
    def __init__(self):
        self.iprs = IPRSVerification()
        self.fifa = FIFAConnectVerification()
    
    def verify_player_comprehensive(self, player_data):
        """
        Comprehensive player verification using all available sources
        
        Args:
            player_data: dict with player information
        
        Returns:
            dict: Combined verification results
        """
        results = {
            'overall_valid': True,
            'iprs_result': None,
            'fifa_result': None,
            'warnings': [],
            'errors': [],
            'verified_data': {}
        }
        
        # 1. Verify ID with IPRS
        if player_data.get('id_number'):
            iprs_result = self.iprs.verify_id_number(
                player_data['id_number'],
                full_name=f"{player_data['first_name']} {player_data['last_name']}",
                date_of_birth=player_data.get('date_of_birth')
            )
            results['iprs_result'] = iprs_result
            
            if not iprs_result['valid']:
                results['overall_valid'] = False
                results['errors'].extend(iprs_result['errors'])
            
            if iprs_result['data']:
                results['verified_data']['iprs'] = iprs_result['data']
        
        # 2. Verify with FIFA Connect
        fifa_result = self.fifa.verify_player(player_data)
        results['fifa_result'] = fifa_result
        
        if not fifa_result['valid']:
            results['overall_valid'] = False
            results['errors'].extend(fifa_result['errors'])
        
        if fifa_result['data']:
            results['verified_data']['fifa'] = fifa_result['data']
        
        # 3. Cross-check data consistency
        if results['iprs_result'] and results['fifa_result']:
            if (results['iprs_result'].get('data') and 
                results['fifa_result'].get('data')):
                
                iprs_dob = results['iprs_result']['data'].get('date_of_birth')
                fifa_dob = results['fifa_result']['data'].get('date_of_birth')
                
                if iprs_dob != fifa_dob:
                    results['warnings'].append(
                        f"Date of birth mismatch between IPRS and FIFA Connect"
                    )
        
        return results


# Async verification for better UX (optional, requires Celery)
def verify_player_async(player_id):
    """
    Background task to verify player after registration
    Use with Celery for async processing
    """
    from teams.models import Player
    
    try:
        player = Player.objects.get(id=player_id)
        orchestrator = VerificationOrchestrator()
        
        player_data = {
            'first_name': player.first_name,
            'last_name': player.last_name,
            'date_of_birth': player.date_of_birth,
            'id_number': player.id_number,
            'nationality': player.nationality,
        }
        
        results = orchestrator.verify_player_comprehensive(player_data)
        
        # Store verification results
        # You could add a JSONField to Player model to store this
        # player.verification_results = results
        # player.is_verified = results['overall_valid']
        # player.save()
        
        return results
    
    except Player.DoesNotExist:
        return {'error': 'Player not found'}
