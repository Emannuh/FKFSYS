"""
Django settings for the FKF Meru League project.

All environment-specific values are read from environment variables (a local
``.env`` file is loaded automatically). The defaults are secure: DEBUG is off
unless ``DJANGO_DEBUG=1`` is set, and production-only protections switch on
automatically whenever DEBUG is off. See ``.env.example`` for every variable.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# ── Core ───────────────────────────────────────────────────────────────────
DEBUG = env_bool("DJANGO_DEBUG")

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is off.")
    from django.core.management.utils import get_random_secret_key

    SECRET_KEY = get_random_secret_key()  # dev only: sessions reset on restart

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]" if DEBUG else ""
)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000" if DEBUG else "https://fkfmeru.co.ke")


# ── Applications ───────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crispy_forms",
    "crispy_bootstrap5",
    "import_export",
    "teams.apps.TeamsConfig",
    "payments",
    "matches.apps.MatchesConfig",
    "referees",
    "admin_dashboard",
    "frontend",
    "tournaments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "referees.middleware.RefereeApprovalCheck",
    "admin_dashboard.activity_middleware.ActivityLoggingMiddleware",
]

ROOT_URLCONF = "fkf_league.urls"
WSGI_APPLICATION = "fkf_league.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "fkf_league.context_processors.league_settings_context",
                "fkf_league.context_processors.site_info_context",
            ],
            # fkf_league is the project package, not an installed app, so its
            # template tag library must be registered explicitly.
            "libraries": {"fkf_tags": "fkf_league.templatetags.fkf_tags"},
        },
    },
]


# ── Database ───────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {"transaction_mode": "IMMEDIATE"},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── Authentication ─────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "frontend:home"

SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True


# ── Internationalisation ───────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True


# ── Static & media ─────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024


# ── Third-party ────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MPESA_CONFIG = {
    "CONSUMER_KEY": os.environ.get("MPESA_CONSUMER_KEY"),
    "CONSUMER_SECRET": os.environ.get("MPESA_CONSUMER_SECRET"),
    "SHORTCODE": os.environ.get("MPESA_SHORTCODE"),
    "PASSKEY": os.environ.get("MPESA_PASSKEY"),
    "CALLBACK_URL": os.environ.get("MPESA_CALLBACK_URL"),
    "ENVIRONMENT": os.environ.get("MPESA_ENVIRONMENT", "sandbox"),
}
# Optional source-IP allow-list for the Daraja callback (empty = token check only).
MPESA_CALLBACK_ALLOWED_IPS = env_list("MPESA_CALLBACK_ALLOWED_IPS")

# Audit log: whether to trust X-Forwarded-For for client IPs. When unset, the
# audit logger trusts it only if SECURE_PROXY_SSL_HEADER is configured.
if "AUDIT_TRUST_X_FORWARDED_FOR" in os.environ:
    AUDIT_TRUST_X_FORWARDED_FOR = env_bool("AUDIT_TRUST_X_FORWARDED_FOR")


# ── Email ──────────────────────────────────────────────────────────────────
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "FKF Meru League <noreply@fkfmeru.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@fkfmeru.com")
ADMINS = [("FKF Admin", ADMIN_EMAIL)]


# ── Security (always on) ───────────────────────────────────────────────────
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# ── Security (production — whenever DEBUG is off) ──────────────────────────
if not DEBUG:
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set when DEBUG is off.")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# ── Logging ────────────────────────────────────────────────────────────────
LOGS_DIR = Path(os.environ.get("LOGS_DIR", BASE_DIR / "logs"))
LOGS_DIR.mkdir(parents=True, exist_ok=True)

_APP_LEVEL = "DEBUG" if DEBUG else "WARNING"
_APP_HANDLERS = ["console", "file"] if DEBUG else ["file", "mail_admins"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name} {message}", "style": "{"},
        "simple": {"format": "{levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "fkf.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "mail_admins": {"level": "ERROR", "class": "django.utils.log.AdminEmailHandler"},
    },
    "loggers": {
        **{
            app: {"handlers": _APP_HANDLERS, "level": _APP_LEVEL, "propagate": False}
            for app in ("teams", "matches", "referees", "admin_dashboard", "payments", "tournaments", "frontend", "fkf_league")
        },
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console", "file", "mail_admins"], "level": "ERROR", "propagate": False},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}
