"""
fkf_league/settings_production.py

Production overrides — import base settings then tighten security.
Usage:
    DJANGO_SETTINGS_MODULE=fkf_league.settings_production python manage.py ...
    or set it in your WSGI/ASGI entrypoint.
"""
from .settings import *  # noqa: F401, F403
import os

# ── Security ───────────────────────────────────────────────────────────────
DEBUG = False
SECRET_KEY = os.environ['SECRET_KEY']           # Must be set in environment

ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS', 'fkfmeru.co.ke,www.fkfmeru.co.ke'
).split(',')

# HTTPS settings
SECURE_SSL_REDIRECT          = True
SECURE_HSTS_SECONDS          = 31536000        # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD          = True
SECURE_PROXY_SSL_HEADER      = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE        = True
CSRF_COOKIE_SECURE           = True
X_FRAME_OPTIONS              = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF  = True
SECURE_BROWSER_XSS_FILTER    = True

# ── Database ───────────────────────────────────────────────────────────────
# Override to use PostgreSQL in production (recommended over SQLite)
# Uncomment and configure when ready:
#
# import dj_database_url
# DATABASES = {
#     'default': dj_database_url.config(
#         default=os.environ['DATABASE_URL'],
#         conn_max_age=600,
#         ssl_require=True,
#     )
# }

# ── Email ──────────────────────────────────────────────────────────────────
EMAIL_BACKEND      = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST         = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT         = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS      = True
EMAIL_HOST_USER    = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'FKF Meru League <noreply@fkfmeru.com>')

# ── Logging — production tightens levels ──────────────────────────────────
LOGGING['loggers'].update({           # type: ignore[name-defined]
    'teams':           {'handlers': ['file', 'mail_admins'], 'level': 'WARNING', 'propagate': False},
    'matches':         {'handlers': ['file', 'mail_admins'], 'level': 'WARNING', 'propagate': False},
    'referees':        {'handlers': ['file', 'mail_admins'], 'level': 'WARNING', 'propagate': False},
    'admin_dashboard': {'handlers': ['file', 'mail_admins'], 'level': 'WARNING', 'propagate': False},
    'payments':        {'handlers': ['file', 'mail_admins'], 'level': 'WARNING', 'propagate': False},
    'tournaments':     {'handlers': ['file', 'mail_admins'], 'level': 'WARNING', 'propagate': False},
    'django.request':  {'handlers': ['file', 'mail_admins'], 'level': 'ERROR',   'propagate': False},
})

# ── Site URL ───────────────────────────────────────────────────────────────
SITE_URL = os.environ.get('SITE_URL', 'https://fkfmeru.co.ke')

# ── Static / Media (WhiteNoise or S3 in production) ───────────────────────
STATIC_URL  = '/static/'
MEDIA_URL   = '/media/'
