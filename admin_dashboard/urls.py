from django.urls import path

from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    # League operations
    path('approve-registrations/', views.approve_registrations, name='approve_registrations'),
    path('approve-reports/', views.approve_reports, name='approve_reports'),
    path('suspensions/', views.view_suspensions, name='view_suspensions'),
    path('suspensions/manage/<int:player_id>/', views.manage_suspension, name='manage_suspension'),
    path('statistics/', views.statistics_dashboard, name='statistics_dashboard'),
    path('assign-zones/', views.assign_zones, name='assign_zones'),
    path('view-report/<int:report_id>/', views.view_report, name='view_report'),
    path('generate-fixtures/', views.generate_fixtures_admin, name='generate_fixtures_admin'),
    path('reschedule-fixtures/', views.reschedule_fixtures_admin, name='reschedule_fixtures_admin'),

    # Audit trail (read-only)
    path('activity-logs/', views.activity_logs, name='activity_logs'),
    path('activity-logs/<int:log_id>/', views.activity_log_detail, name='activity_log_detail'),

    # Registration windows
    path('toggle-registration/', views.toggle_registration_window, name='toggle_registration'),
    path('update-deadlines/', views.update_registration_deadlines, name='update_deadlines'),

    # Transfers
    path('transfers/', views.manage_transfers, name='manage_transfers'),
    path('transfers/override/<int:transfer_id>/', views.admin_override_transfer, name='override_transfer'),

    # User management (superuser only)
    path('users/', views.manage_league_admins, name='manage_league_admins'),
    path('users/create/', views.create_league_admin, name='create_league_admin'),
    path('users/toggle/<int:user_id>/', views.toggle_league_admin_status, name='toggle_league_admin_status'),
    path('users/reset-password/<int:user_id>/', views.reset_league_admin_password, name='reset_league_admin_password'),
    path('users/edit-roles/<int:user_id>/', views.edit_user_roles, name='edit_user_roles'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
]
