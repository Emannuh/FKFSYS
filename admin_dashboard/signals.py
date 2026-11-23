"""Auth-event audit logging (connected in AdminDashboardConfig.ready)."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .activity_logger import Action, log_activity


@receiver(user_logged_in, dispatch_uid='audit_user_logged_in')
def audit_login(sender, request, user, **kwargs):
    log_activity(user, Action.LOGIN, f"{user.get_username()} logged in", request=request)


@receiver(user_logged_out, dispatch_uid='audit_user_logged_out')
def audit_logout(sender, request, user, **kwargs):
    if user is not None:
        log_activity(user, Action.LOGOUT, f"{user.get_username()} logged out", request=request)


@receiver(user_login_failed, dispatch_uid='audit_user_login_failed')
def audit_login_failed(sender, credentials, request=None, **kwargs):
    # Django already masks the password in ``credentials``; only the attempted
    # username is kept.
    attempted = str(credentials.get('username', ''))[:150]
    log_activity(
        None, Action.LOGIN_FAILED, "Failed login attempt",
        request=request, extra_data={'attempted_username': attempted},
    )
