# Email Configuration Guide for FKF League System

## Current Setup (Development)

The system is currently configured to display emails in the console for testing purposes.

## Features Implemented

### 1. Welcome Email (New User Creation)
- Sent automatically when a Super Admin creates a new user
- Contains:
  - Username
  - Temporary password
  - User role
  - Login URL
  - Password change instructions
  - Security tips

### 2. Password Reset Email
- Sent when a Super Admin resets a user's password
- Contains:
  - Username
  - New password
  - User role
  - Login URL
  - Password change instructions
  - Security reminder

### 3. Email Formats
- **Plain Text**: For all email clients
- **HTML**: Beautiful styled emails with colors and formatting

## Testing in Development

Currently, emails are printed to the console/terminal where Django is running:

```bash
# When you create a user or reset password, check the terminal output
# You'll see the full email content displayed there
```

## Production Configuration

### Option 1: Gmail SMTP (Recommended for Small Scale)

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Create App Password**:
   - Go to Google Account Settings
   - Security → 2-Step Verification → App Passwords
   - Generate password for "Mail"
   - Copy the 16-character password

3. **Update `settings.py`**:

```python
# Comment out the console backend
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Enable SMTP backend
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-16-char-app-password'
DEFAULT_FROM_EMAIL = 'FKF Meru League <your-email@gmail.com>'
SITE_URL = 'https://your-production-domain.com'
```

### Option 2: Office 365/Outlook

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.office365.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@outlook.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'FKF Meru League <your-email@outlook.com>'
```

### Option 3: SendGrid (Recommended for Production)

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = 'your-sendgrid-api-key'
DEFAULT_FROM_EMAIL = 'FKF Meru League <noreply@yourdomain.com>'
```

### Option 4: Amazon SES

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'email-smtp.us-east-1.amazonaws.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-ses-smtp-username'
EMAIL_HOST_PASSWORD = 'your-ses-smtp-password'
DEFAULT_FROM_EMAIL = 'FKF Meru League <noreply@yourdomain.com>'
```

## Security Best Practices

### Using Environment Variables (Recommended)

Never hardcode passwords in `settings.py`. Use environment variables:

1. **Install python-decouple**:
```bash
pip install python-decouple
```

2. **Create `.env` file** (in project root):
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
SITE_URL=http://localhost:8000
```

3. **Update `settings.py`**:
```python
from decouple import config

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT', cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = f'FKF Meru League <{config("EMAIL_HOST_USER")}>'
SITE_URL = config('SITE_URL', default='http://localhost:8000')
```

4. **Add to `.gitignore`**:
```
.env
```

## Testing Email Functionality

### Test in Console (Development)
```bash
# Run Django server
python manage.py runserver

# In another terminal, check the output when creating users
# Emails will be printed to the console
```

### Test in Production
1. Create a test user with your email
2. Check your inbox (and spam folder)
3. Verify the email contains:
   - Correct login credentials
   - Working login link
   - Proper formatting

## Troubleshooting

### Emails Not Sending

1. **Check Gmail Settings**:
   - Enable "Less secure app access" OR use App Passwords
   - Check 2-Factor Authentication

2. **Firewall Issues**:
   - Ensure port 587 (or 465) is not blocked
   - Try using EMAIL_USE_SSL = True with port 465

3. **Debug Mode**:
```python
# Add to settings.py temporarily
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# This will show emails in console to verify they're being generated
```

4. **Check Logs**:
```python
# In views.py, the functions print errors:
# Check terminal for error messages
```

### HTML Emails Not Displaying

- Some email clients block HTML
- Plain text version is always included as fallback
- Check spam folder - HTML emails sometimes trigger spam filters

## Email Templates Location

- Welcome Email: `templates/emails/welcome_email.html`
- Password Reset: `templates/emails/password_reset.html`

You can customize these templates to match your branding.

## Daily Limits

**Gmail**: 500 emails per day
**SendGrid Free**: 100 emails per day
**Amazon SES**: 200 emails per day (free tier)

For production with many users, consider SendGrid or AWS SES paid plans.

## Support

For issues or questions:
- Check Django email documentation: https://docs.djangoproject.com/en/4.2/topics/email/
- Verify SMTP settings with your email provider
- Test with a simple script first before using in production
