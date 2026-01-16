# referees/urls.py
from django.urls import path
from . import views
from . import matchday_views

app_name = 'referees'

urlpatterns = [
    # Public
    path('register/', views.referee_registration, name='referee_registration'),
    path('login-instructions/', views.login_instructions, name='login_instructions'),
    
    # Referee Dashboard & Profile
    path('dashboard/', views.referee_dashboard, name='referee_dashboard'),
    path('profile/', views.referee_profile, name='referee_profile'),
    path('availability/', views.referee_availability, name='referee_availability'),
    path('report/<int:report_id>/', views.view_report, name='view_report'),
    
    # Referee Actions
    path('match/<int:match_id>/confirm/', views.confirm_appointment, name='confirm_appointment'),
    path('match/<int:match_id>/decline/', views.decline_appointment, name='decline_appointment'),
    path('match/<int:match_id>/quick-report/', views.submit_match_report, name='submit_match_report'),
    path('match/<int:match_id>/comprehensive-report/', views.submit_comprehensive_report, name='submit_comprehensive_report'),
    path('match/<int:match_id>/cancel/', views.cancel_appointment, name='cancel_appointment'),
    
    # Matchday Squad Management - Team Manager
    path('matchday/squads/', matchday_views.team_matchday_squad_list, name='team_matchday_squad_list'),
    path('matchday/squad/submit/<int:match_id>/', matchday_views.submit_matchday_squad, name='submit_matchday_squad'),
    path('matchday/substitution/request/<int:match_id>/', matchday_views.team_request_substitution, name='team_request_substitution'),
    
    # Matchday Squad Management - Main Referee
    path('matchday/referee/approvals/', matchday_views.referee_squad_approval_list, name='referee_squad_approval_list'),
    path('matchday/referee/approve/<int:match_id>/', matchday_views.approve_matchday_squads, name='approve_matchday_squads'),
    
    # Matchday Squad Management - Fourth Official / Reserve Referee
    path('matchday/fourth-official/<int:match_id>/', matchday_views.fourth_official_substitutions, name='fourth_official_substitutions'),
    path('matchday/concussion-sub/<int:match_id>/', matchday_views.activate_concussion_substitute, name='activate_concussion_substitute'),
    
    # Manager Report Approval
    path('reports/pending/', views.pending_reports, name='pending_reports'),
    path('reports/<int:report_id>/approve/', views.approve_report, name='approve_report'),
    path('reports/<int:report_id>/reject/', views.reject_report, name='reject_report'),
    path('reports/<int:report_id>/view/', views.report_detail_view, name='report_detail_view'),
    
    # Pre-Match Meeting Form
    path('match/<int:match_id>/prematch-form/', views.submit_prematch_form, name='submit_prematch_form'),
    path('prematch-form/<int:form_id>/view/', views.view_prematch_form, name='view_prematch_form'),
    path('prematch-form/<int:form_id>/admin-approve/', views.admin_approve_prematch_form, name='admin_approve_prematch_form'),
    path('prematch-form/<int:form_id>/manager-approve/', views.manager_approve_prematch_form, name='manager_approve_prematch_form'),
    path('prematch-forms/pending-admin/', views.pending_prematch_forms_admin, name='pending_prematch_forms_admin'),
    path('prematch-forms/pending-manager/', views.pending_prematch_forms_manager, name='pending_prematch_forms_manager'),
    
    # Referees Manager Actions
    path('matches/needing-officials/', views.matches_needing_officials, name='matches_needing_officials'),
    path('match/<int:match_id>/appoint/', views.appoint_match_officials, name='appoint_match_officials'),
    path('match/<int:match_id>/replace/<str:role>/', views.replace_referee, name='replace_referee'),
    
    # Admin Management
    path('admin/dashboard/', views.admin_referee_dashboard, name='admin_referee_dashboard'),
    path('admin/pending/', views.pending_referees, name='pending_referees'),
    path('admin/all/', views.all_referees, name='all_referees'),
    path('admin/approve/<int:referee_id>/', views.approve_referee, name='approve_referee'),
    path('admin/reject/<int:referee_id>/', views.reject_referee, name='reject_referee'),
    path('admin/suspend/<int:referee_id>/', views.suspend_referee, name='suspend_referee'),
    path('admin/reactivate/<int:referee_id>/', views.reactivate_referee, name='reactivate_referee'),
    
    # API Endpoints for Referees Manager Dashboard
    path('api/urgent-matches/', views.api_urgent_matches, name='api_urgent_matches'),
    path('api/appointed-matches/', views.api_appointed_matches, name='api_appointed_matches'),
    path('api/recent-appointments/', views.api_recent_appointments, name='api_recent_appointments'),
    path('api/available-referees-today/', views.api_available_referees_today, name='api_available_referees_today'),
    path('api/manager-stats/', views.api_manager_stats, name='api_manager_stats'),
    path('api/generate-weekly-report/', views.generate_weekly_report, name='generate_weekly_report'),
    
    # HTML Display for Weekly Report
    path('weekly-report-display/', views.weekly_report_display, name='weekly_report_display'),
    
    # Export Endpoints
    path('export/excel/', views.export_appointments_excel, name='export_appointments_excel'),
    path('export/pdf/', views.export_appointments_pdf, name='export_appointments_pdf'),
]