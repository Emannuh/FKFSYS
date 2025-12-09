# admin_dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('approve-registrations/', views.approve_registrations, name='approve_registrations'),
    path('approve-reports/', views.approve_reports, name='approve_reports'),
    path('suspensions/', views.view_suspensions, name='view_suspensions'),
    path('suspensions/manage/<int:player_id>/', views.manage_suspension, name='manage_suspension'),
    path('statistics/', views.statistics_dashboard, name='statistics_dashboard'),
    path('assign-zones/', views.assign_zones, name='assign_zones'),
]