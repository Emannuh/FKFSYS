"""
admin_dashboard/email.py

All transactional emails for the admin dashboard.
Keeps views.py free of email composition logic.
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


def _send(subject, text_content, html_template, html_context, recipient_email):
    """Base helper — compose and send one email, returning True on success."""
    html_content = None
    try:
        html_content = render_to_string(html_template, html_context)
    except Exception:
        pass  # fall back to plain text

    try:
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
        )
        if html_content:
            email.attach_alternative(html_content, 'text/html')
        email.send(fail_silently=False)
        return True
    except Exception as exc:
        print(f"[email] Failed to send to {recipient_email}: {exc}")  # noqa: T201
        return False


def send_welcome_email(user, password, role):
    """
    Send login credentials to a newly created user.
    Previously a free function buried inside admin_dashboard/views.py.
    """
    login_url = f'{settings.SITE_URL}/accounts/login/'
    subject = f'Welcome to FKF Meru League Management System — {role}'

    text_content = (
        f"Dear {user.get_full_name() or user.username},\n\n"
        f"Your account has been created.\n\n"
        f"Username: {user.username}\n"
        f"Temporary Password: {password}\n"
        f"Role: {role}\n"
        f"Login: {login_url}\n\n"
        f"Please change your password immediately after first login.\n\n"
        f"FKF Meru County League Administration"
    )

    return _send(
        subject=subject,
        text_content=text_content,
        html_template='emails/welcome_email.html',
        html_context={
            'user': user,
            'username': user.username,
            'password': password,
            'role': role,
            'login_url': login_url,
        },
        recipient_email=user.email,
    )


def send_password_reset_email(user, new_password):
    """
    Notify a user that their password was reset by an admin.
    Previously a free function buried inside admin_dashboard/views.py.
    """
    login_url = f'{settings.SITE_URL}/accounts/login/'
    roles = ', '.join(user.groups.values_list('name', flat=True)) or 'N/A'
    subject = 'FKF Meru League — Password Reset'

    text_content = (
        f"Dear {user.get_full_name() or user.username},\n\n"
        f"Your password has been reset by an administrator.\n\n"
        f"Username: {user.username}\n"
        f"New Password: {new_password}\n"
        f"Login: {login_url}\n\n"
        f"Please change your password immediately after logging in.\n\n"
        f"FKF Meru County League Administration"
    )

    return _send(
        subject=subject,
        text_content=text_content,
        html_template='emails/password_reset.html',
        html_context={
            'user': user,
            'username': user.username,
            'password': new_password,
            'roles': roles,
            'login_url': login_url,
        },
        recipient_email=user.email,
    )


def send_transfer_notification(transfer, recipient_team):
    """Notify a team manager about a new incoming transfer request."""
    subject = f'Transfer Request — {transfer.player.full_name}'
    text_content = (
        f"{transfer.to_team.team_name} has requested to transfer "
        f"{transfer.player.full_name} (#{transfer.player.jersey_number}) "
        f"from your squad.\n\n"
        f"Please log in to review and respond.\n\n"
        f"FKF Meru County League"
    )
    manager = getattr(recipient_team, 'manager', None)
    if not manager or not manager.email:
        return False

    return _send(
        subject=subject,
        text_content=text_content,
        html_template='emails/transfer_notification.html',
        html_context={'transfer': transfer},
        recipient_email=manager.email,
    )
