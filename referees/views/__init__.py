"""Referees views, split by feature. Re-exported so ``views.<name>`` keeps working."""
from .accounts import (  # noqa: F401
    admin_referee_dashboard, all_referees, approve_referee, login_instructions, pending_referees,
    reactivate_referee, referee_availability, referee_profile, referee_registration, reject_referee,
    suspend_referee,
)
from .appointments import (  # noqa: F401
    api_appointed_matches, api_available_referees_today, api_urgent_matches, appoint_match_officials,
    cancel_appointment, confirm_appointment, decline_appointment, matches_needing_officials,
    referee_dashboard, replace_referee,
)
from .matchday import (  # noqa: F401
    activate_concussion_substitute, approve_matchday_squads, referee_review_squad_edit_requests,
    referee_squad_approval_list, reserve_referee_substitutions, submit_matchday_squad,
    team_matchday_squad_list, team_request_squad_edit, team_request_substitution,
)
from .prematch import (  # noqa: F401
    admin_approve_prematch_form, manager_approve_prematch_form, pending_prematch_forms_admin,
    pending_prematch_forms_manager, submit_prematch_form, view_prematch_form,
)
from .reports import (  # noqa: F401
    approve_report, pending_reports, reject_report, report_detail_view, submit_comprehensive_report,
    submit_match_report, view_report,
)
from .weekly import export_appointments_excel, generate_weekly_report, weekly_report_display  # noqa: F401
