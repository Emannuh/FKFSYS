"""Audit trail (SOC2): an append-only record of security-relevant user actions.

Rows are written only through ``admin_dashboard.activity_logger.log_activity``
(and the request middleware / auth signal handlers that call it). The model and
its queryset refuse in-place updates and deletes so application code cannot
tamper with the trail; retention purges must be done by an operator at the
database level.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class AuditLogImmutableError(Exception):
    """Raised when code tries to modify or delete an existing audit row."""


class ActivityLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AuditLogImmutableError("Activity logs are append-only.")

    def delete(self):
        raise AuditLogImmutableError("Activity logs are append-only.")


class ActivityLog(models.Model):
    class Action(models.TextChoices):
        # Authentication
        LOGIN = 'LOGIN', 'Login'
        LOGIN_FAILED = 'LOGIN_FAILED', 'Login Failed'
        LOGOUT = 'LOGOUT', 'Logout'
        PASSWORD_CHANGE = 'PASSWORD_CHANGE', 'Password Change'
        ACCESS_DENIED = 'ACCESS_DENIED', 'Access Denied'

        # Team management
        TEAM_CREATE = 'TEAM_CREATE', 'Team Created'
        TEAM_UPDATE = 'TEAM_UPDATE', 'Team Updated'
        TEAM_DELETE = 'TEAM_DELETE', 'Team Deleted'
        TEAM_APPROVE = 'TEAM_APPROVE', 'Team Approved'
        TEAM_REJECT = 'TEAM_REJECT', 'Team Rejected'
        TEAM_SUSPEND = 'TEAM_SUSPEND', 'Team Suspended'

        # Player management
        PLAYER_CREATE = 'PLAYER_CREATE', 'Player Created'
        PLAYER_UPDATE = 'PLAYER_UPDATE', 'Player Updated'
        PLAYER_DELETE = 'PLAYER_DELETE', 'Player Deleted'
        PLAYER_TRANSFER = 'PLAYER_TRANSFER', 'Player Transfer'
        TRANSFER_OVERRIDE = 'TRANSFER_OVERRIDE', 'Transfer Overridden by Admin'

        # Match management
        MATCH_CREATE = 'MATCH_CREATE', 'Match Created'
        MATCH_UPDATE = 'MATCH_UPDATE', 'Match Updated'
        MATCH_DELETE = 'MATCH_DELETE', 'Match Deleted'
        MATCH_RESCHEDULE = 'MATCH_RESCHEDULE', 'Match Rescheduled'
        MATCH_REPORT = 'MATCH_REPORT', 'Match Report Submitted'
        MATCH_REPORT_APPROVE = 'MATCH_REPORT_APPROVE', 'Match Report Approved'
        MATCH_REPORT_REJECT = 'MATCH_REPORT_REJECT', 'Match Report Rejected'

        # Fixtures
        FIXTURE_GENERATE = 'FIXTURE_GENERATE', 'Fixtures Generated'
        FIXTURE_REGENERATE = 'FIXTURE_REGENERATE', 'Fixtures Regenerated'
        FIXTURE_DELETE = 'FIXTURE_DELETE', 'Fixtures Deleted'

        # Zones
        ZONE_ASSIGN = 'ZONE_ASSIGN', 'Zone Assigned'
        ZONE_UPDATE = 'ZONE_UPDATE', 'Zone Updated'

        # Payments
        PAYMENT_RECEIVED = 'PAYMENT_RECEIVED', 'Payment Received'
        PAYMENT_VERIFIED = 'PAYMENT_VERIFIED', 'Payment Verified'
        PAYMENT_ACTION = 'PAYMENT_ACTION', 'Payment Action'

        # Suspensions
        SUSPENSION_CREATE = 'SUSPENSION_CREATE', 'Suspension Created'
        SUSPENSION_LIFT = 'SUSPENSION_LIFT', 'Suspension Lifted'

        # Matchday squads
        MATCHDAY_SQUAD_SUBMIT = 'MATCHDAY_SQUAD_SUBMIT', 'Matchday Squad Submitted'
        SQUAD_APPROVE = 'SQUAD_APPROVE', 'Squad Approved'
        SQUAD_REJECT = 'SQUAD_REJECT', 'Squad Rejected'

        # Referees
        REFEREE_REGISTER = 'REFEREE_REGISTER', 'Referee Registered'
        REFEREE_APPROVE = 'REFEREE_APPROVE', 'Referee Approved'
        REFEREE_ACTION = 'REFEREE_ACTION', 'Referee Action'

        # User management
        USER_CREATE = 'USER_CREATE', 'User Created'
        USER_UPDATE = 'USER_UPDATE', 'User Updated'
        USER_DELETE = 'USER_DELETE', 'User Deleted'
        USER_ROLE_CHANGE = 'USER_ROLE_CHANGE', 'User Role Changed'
        USER_ACTIVATE = 'USER_ACTIVATE', 'User Activated'
        USER_DEACTIVATE = 'USER_DEACTIVATE', 'User Deactivated'
        PASSWORD_RESET = 'PASSWORD_RESET', 'Password Reset by Admin'

        # System
        CONFIG_CHANGE = 'CONFIG_CHANGE', 'Configuration Changed'
        REGISTRATION_TOGGLE = 'REGISTRATION_TOGGLE', 'Registration Window Toggled'
        ADMIN_ACTION = 'ADMIN_ACTION', 'Admin Action'
        OTHER = 'OTHER', 'Other Action'

    # Who performed the action
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs',
    )

    # What was done
    action = models.CharField(max_length=50, choices=Action.choices)
    description = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    # Affected object
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    object_repr = models.CharField(max_length=200, blank=True)

    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    # Structured, non-sensitive context (field names, ids, counts — never values
    # of submitted forms, never secrets).
    extra_data = models.JSONField(default=dict, blank=True)

    # Legacy columns, no longer written. ``changes_json`` held raw POST bodies
    # (may contain PII in old rows) and the undo columns belonged to an undo
    # feature that never recorded an undoable action. Kept to avoid a
    # destructive migration; see the modernisation report.
    changes_json = models.TextField(blank=True, default='{}', help_text="Legacy: no longer written")
    previous_state = models.JSONField(null=True, blank=True, help_text="Legacy: no longer written")
    new_state = models.JSONField(null=True, blank=True, help_text="Legacy: no longer written")
    can_undo = models.BooleanField(default=False, help_text="Legacy: no longer written")
    is_undone = models.BooleanField(default=False, help_text="Legacy: no longer written")
    undone_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='undone_actions',
    )
    undo_reason = models.TextField(blank=True)

    objects = ActivityLogQuerySet.as_manager()

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'

    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.timestamp:%Y-%m-%d %H:%M:%S}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AuditLogImmutableError("Activity logs are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditLogImmutableError("Activity logs are append-only.")

    # ── Presentation helpers (used by the activity log templates) ──────────
    @property
    def action_class(self) -> str:
        """Bootstrap colour class for the action badge."""
        action = self.action.upper()
        if any(w in action for w in ('DELETE', 'SUSPEND', 'REJECT', 'REGENERATE', 'DENIED', 'FAILED', 'DEACTIVATE')):
            return 'danger'
        if any(w in action for w in ('UPDATE', 'RESCHEDULE', 'TRANSFER', 'RESET', 'ROLE', 'OVERRIDE')):
            return 'warning'
        if any(w in action for w in ('CREATE', 'APPROVE', 'GENERATE', 'ACTIVATE')):
            return 'success'
        if 'LOGIN' in action or 'LOGOUT' in action:
            return 'info'
        return 'secondary'

    @property
    def action_icon(self) -> str:
        """Font Awesome icon name for the action badge."""
        icon_map = {
            'LOGIN_FAILED': 'user-lock',
            'LOGIN': 'sign-in-alt',
            'LOGOUT': 'sign-out-alt',
            'DENIED': 'lock',
            'CREATE': 'plus-circle',
            'UPDATE': 'edit',
            'DELETE': 'trash',
            'APPROVE': 'check-circle',
            'REJECT': 'times-circle',
            'SUSPEND': 'ban',
            'TRANSFER': 'exchange-alt',
            'GENERATE': 'random',
            'PAYMENT': 'money-bill',
            'PASSWORD': 'key',
            'ROLE': 'user-tag',
        }
        action = self.action.upper()
        for key, icon in icon_map.items():
            if key in action:
                return icon
        return 'info-circle'
