# teams/urls.py
from django.urls import path
from . import admin_dashboard   
from . import views

app_name = 'teams'  # Add this line

# teams/urls.py - Update the urlpatterns
urlpatterns = [
    path('register/', views.team_registration, name='team_registration'),
    path('add-players/', views.add_players, name='add_players'),
    path('dashboard/<int:team_id>/', views.team_dashboard, name='team_dashboard'),
    path('all/', views.all_teams, name='all_teams'),
    path('admin-dashboard/', admin_dashboard.admin_dashboard, name='admin_dashboard'),
    path('detail/<int:team_id>/', views.team_detail, name='team_detail'),
]