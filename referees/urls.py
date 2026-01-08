# referees/urls.py
from django.urls import path
from . import views

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
    path('match/<int:match_id>/quick-report/', views.submit_match_report, name='submit_match_report'),
    path('match/<int:match_id>/comprehensive-report/', views.submit_comprehensive_report, name='submit_comprehensive_report'),
    
    # Manager Report Approval
    path('reports/pending/', views.pending_reports, name='pending_reports'),
    path('reports/<int:report_id>/approve/', views.approve_report, name='approve_report'),
    path('reports/<int:report_id>/reject/', views.reject_report, name='reject_report'),
    path('reports/<int:report_id>/view/', views.report_detail_view, name='report_detail_view'),
    
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
    path('api/recent-appointments/', views.api_recent_appointments, name='api_recent_appointments'),
    path('api/available-referees-today/', views.api_available_referees_today, name='api_available_referees_today'),
    path('api/manager-stats/', views.api_manager_stats, name='api_manager_stats'),
    path('api/generate-weekly-report/', views.generate_weekly_report, name='generate_weekly_report'),
    
    # HTML Display for Weekly Report
    path('weekly-report-display/', views.weekly_report_display, name='weekly_report_display'),
]