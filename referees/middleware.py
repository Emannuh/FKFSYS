# referees/middleware.py
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.contrib import messages
import re

class RefereeApprovalCheck:
    """
    Middleware to check if a logged-in referee user has been approved.
    Redirects unapproved referees to login instructions page.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Public URLs that anyone can access
        self.public_urls = [
            'referees:referee_registration',
            'referees:login_instructions',
        ]
        
        # Admin URLs (only accessible by staff)
        self.admin_urls = [
            'referees:pending_referees',
            'referees:approve_referee',
            'referees:reject_referee',
            'referees:all_referees',
        ]
        
        # Authentication URLs
        self.auth_urls = [
            'login',
            'logout',
            'password_reset',
            'password_reset_done',
            'password_reset_confirm',
            'password_reset_complete',
        ]

    def __call__(self, request):
        # Skip middleware for static/media files and admin login
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)
        
        if request.path.startswith('/admin/login/'):
            return self.get_response(request)
        
        # Try to get current URL name
        try:
            current_url = resolve(request.path_info).url_name
            current_namespace = resolve(request.path_info).namespace
            full_url_name = f"{current_namespace}:{current_url}" if current_namespace else current_url
        except:
            # If URL can't be resolved, continue
            full_url_name = None
        
        # If user is not authenticated, let them through
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Staff/admin users can access everything
        if request.user.is_staff or request.user.is_superuser:
            return self.get_response(request)
        
        # Check if accessing public URLs
        if full_url_name in self.public_urls:
            return self.get_response(request)
        
        # Check if accessing auth URLs
        if full_url_name in self.auth_urls:
            return self.get_response(request)
        
        # Check if user has a referee profile
        if not hasattr(request.user, 'referee'):
            # Not a referee, let them through
            return self.get_response(request)
        
        # Now we have a referee user
        referee = request.user.referee
        
        # Check if accessing admin URLs (they shouldn't have access anyway)
        if full_url_name in self.admin_urls:
            return self.get_response(request)
        
        # Check if accessing referee dashboard or profile pages
        if full_url_name in ['referees:referee_dashboard', 'referees:referee_profile', 
                            'referees:referee_matches', 'referees:view_report',
                            'referees:submit_match_report', 'referees:submit_comprehensive_report']:
            
            # Check approval status
            if referee.status == 'pending':
                if full_url_name != 'referees:login_instructions':
                    messages.info(request, 'Your account is pending approval. You will be notified once approved.')
                    return redirect('referees:login_instructions')
            
            elif referee.status == 'rejected':
                if full_url_name != 'referees:login_instructions':
                    messages.error(
                        request, 
                        f'Your application has been rejected. Reason: {referee.rejection_reason or "No reason provided"}'
                    )
                    return redirect('referees:login_instructions')
            
            # If approved, allow access to referee pages
            elif referee.status == 'approved':
                return self.get_response(request)
        
        # For all other URLs, let them through
        return self.get_response(request)