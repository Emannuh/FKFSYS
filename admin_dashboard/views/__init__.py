"""admin_dashboard views, split by feature. Re-exported so ``views.<name>``
(and ``admin_dashboard.views.dashboard`` in the root urlconf) keep working."""
from .activity import activity_log_detail, activity_logs
from .dashboard import dashboard
from .fixtures import generate_fixtures_admin, reschedule_fixtures_admin
from .league import (
    admin_override_transfer,
    approve_registrations,
    approve_reports,
    assign_zones,
    manage_suspension,
    manage_transfers,
    statistics_dashboard,
    toggle_registration_window,
    update_registration_deadlines,
    view_report,
    view_suspensions,
)
from .users import (
    create_league_admin,
    delete_user,
    edit_user_roles,
    manage_league_admins,
    reset_league_admin_password,
    toggle_league_admin_status,
)
