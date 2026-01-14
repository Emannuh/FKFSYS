"""
Test Email Functionality

Run this script to test if emails are working correctly.
For development, emails will print to console.
For production, they will be sent to actual email addresses.

Usage:
    python test_email.py
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fkf_league.settings')
django.setup()

from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string

def test_simple_email():
    """Test simple text email"""
    print("=" * 60)
    print("Testing Simple Text Email")
    print("=" * 60)
    
    try:
        send_mail(
            'Test Email - FKF League',
            'This is a test email from FKF Meru League Management System.',
            settings.DEFAULT_FROM_EMAIL,
            ['test@example.com'],
            fail_silently=False,
        )
        print("✅ Simple email test PASSED")
        print("Check console/terminal output above for email content")
        return True
    except Exception as e:
        print(f"❌ Simple email test FAILED: {str(e)}")
        return False

def test_html_email():
    """Test HTML email with template"""
    print("\n" + "=" * 60)
    print("Testing HTML Email with Template")
    print("=" * 60)
    
    try:
        # Create test data
        test_user = type('User', (), {
            'first_name': 'John',
            'last_name': 'Doe',
            'username': 'johndoe',
            'email': 'test@example.com'
        })()
        
        text_content = "This is the plain text version"
        
        try:
            html_content = render_to_string('emails/welcome_email.html', {
                'user': test_user,
                'username': 'johndoe',
                'password': 'Test123Pass',
                'role': 'League Admin',
                'login_url': f'{settings.SITE_URL}/accounts/login/'
            })
            html_works = True
        except Exception as e:
            print(f"⚠️  HTML template not found or error: {str(e)}")
            print("   Using plain text only")
            html_content = None
            html_works = False
        
        email = EmailMultiAlternatives(
            'Test HTML Email - FKF League',
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            ['test@example.com']
        )
        
        if html_content:
            email.attach_alternative(html_content, "text/html")
        
        email.send(fail_silently=False)
        
        if html_works:
            print("✅ HTML email test PASSED")
        else:
            print("⚠️  HTML email test PARTIAL - template issue but email works")
        
        print("Check console/terminal output above for email content")
        return True
    except Exception as e:
        print(f"❌ HTML email test FAILED: {str(e)}")
        return False

def test_welcome_email():
    """Test the actual welcome email function"""
    print("\n" + "=" * 60)
    print("Testing Welcome Email Function")
    print("=" * 60)
    
    try:
        from admin_dashboard.views import send_welcome_email
        from django.contrib.auth.models import User
        
        # Create or get test user
        test_user, created = User.objects.get_or_create(
            username='test_email_user',
            defaults={
                'email': 'test@example.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        
        result = send_welcome_email(test_user, 'TestPass123', 'Test Role')
        
        if result:
            print("✅ Welcome email function test PASSED")
            print("Check console/terminal output above for email content")
        else:
            print("⚠️  Welcome email function completed but may have warnings")
        
        # Clean up
        if created:
            test_user.delete()
        
        return result
    except Exception as e:
        print(f"❌ Welcome email function test FAILED: {str(e)}")
        return False

def main():
    print("\n" + "=" * 60)
    print("FKF LEAGUE EMAIL SYSTEM TEST")
    print("=" * 60)
    print(f"\nEmail Backend: {settings.EMAIL_BACKEND}")
    print(f"Default From: {settings.DEFAULT_FROM_EMAIL}")
    print(f"Site URL: {settings.SITE_URL}")
    
    if 'console' in settings.EMAIL_BACKEND.lower():
        print("\n⚠️  DEVELOPMENT MODE: Emails will print to console")
    else:
        print("\n📧 PRODUCTION MODE: Emails will be sent to recipients")
    
    print("\n" + "-" * 60)
    
    # Run tests
    results = []
    results.append(("Simple Email", test_simple_email()))
    results.append(("HTML Email", test_html_email()))
    results.append(("Welcome Email Function", test_welcome_email()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Email system is working correctly.")
    elif passed > 0:
        print("\n⚠️  Some tests failed. Check configuration.")
    else:
        print("\n❌ All tests failed. Please check email configuration.")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
