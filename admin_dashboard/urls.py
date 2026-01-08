# admin_dashboard/urls.py
from django.urls import path

from . import views

from . import admin_views
from . import reschedule_admin_views


urlpatterns = [
    path('', views.dashboard, name='dashboard'),  # ADD THIS - main dashboard
    path('admin/', views.admin_dashboard, name='admin_dashboard'),  # Rename this
    path('approve-registrations/', views.approve_registrations, name='approve_registrations'),
    path('approve-reports/', views.approve_reports, name='approve_reports'),
    path('suspensions/', views.view_suspensions, name='view_suspensions'),
    path('suspensions/manage/<int:player_id>/', views.manage_suspension, name='manage_suspension'),
    path('statistics/', views.statistics_dashboard, name='statistics_dashboard'),
    path('assign-zones/', views.assign_zones, name='assign_zones'),
    path('view-report/<int:report_id>/', views.view_report, name='view_report'),
    path('generate-fixtures/', admin_views.generate_fixtures_admin, name='generate_fixtures_admin'),
    path('reschedule-fixtures/', reschedule_admin_views.reschedule_fixtures_admin, name='reschedule_fixtures_admin'),
    
    # Registration Window Controls
    path('toggle-registration/', views.toggle_registration_window, name='toggle_registration'),
    path('update-deadlines/', views.update_registration_deadlines, name='update_deadlines'),
    
    # Transfer Management
    path('transfers/', views.manage_transfers, name='manage_transfers'),
    path('transfers/override/<int:transfer_id>/', views.admin_override_transfer, name='override_transfer'),
]

app_name = 'admin_dashboard'