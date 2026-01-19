# teams/urls.py - REPLACE ENTIRE FILE

from django.urls import path
from . import admin_dashboard   
from . import views
from .edit_team_info_view import edit_team_info

app_name = 'teams'

urlpatterns = [
    # Registration (available to all)
    path('register/', views.team_registration, name='team_registration'),
    path('registration-success/', views.registration_success, name='registration_success'),
    
    # After approval only
    path('select-kit/', views.select_kit_colors, name='select_kit_colors'),
    path('team-officials/', views.team_officials, name='team_officials'),
    path('delete-official/<int:official_id>/', views.delete_official, name='delete_official'),
    path('manager-dashboard/', views.team_manager_dashboard, name='team_manager_dashboard'),
    path('view-squad/<int:match_id>/', views.view_approved_squad, name='view_approved_squad'),
    path('update-kits/<int:team_id>/', views.update_team_kits, name='update_kits'),
    path('add-players-approved/', views.add_players_to_approved_team, name='add_players_approved'),
    path('add-player-action/', views.add_player_action, name='add_player_action'),

    # Edit team info (League Admin/Manager)
    path('edit-info/<int:team_id>/', edit_team_info, name='edit_team_info'),
    
    # Transfer System
    path('search-players/', views.search_players, name='search_players'),
    path('request-transfer/<int:player_id>/', views.request_transfer, name='request_transfer'),
    path('my-transfers/', views.my_transfer_requests, name='my_transfer_requests'),
    path('approve-transfer/<int:transfer_id>/', views.approve_transfer, name='approve_transfer'),
    path('reject-transfer/<int:transfer_id>/', views.reject_transfer, name='reject_transfer'),
    path('cancel-transfer/<int:transfer_id>/', views.cancel_transfer, name='cancel_transfer'),
    
    # Admin/Public views
    path('all/', views.all_teams, name='all_teams'),
    path('admin-dashboard/', admin_dashboard.admin_dashboard, name='admin_dashboard'),
    path('detail/<int:team_id>/', views.team_detail, name='team_detail'),
    path('team-dashboard/<int:team_id>/', views.team_dashboard, name='team_dashboard'),
    path('admin-team-dashboard/', views.league_admin_dashboard, name='dashboard'),
    
    # Admin Player Management
    path('admin/players/', views.admin_manage_players, name='admin_manage_players'),
    path('admin/player/<int:player_id>/edit/', views.admin_edit_player, name='admin_edit_player'),
    path('admin/player/<int:player_id>/delete/', views.admin_delete_player, name='admin_delete_player'),
    path('admin/player/<int:player_id>/suspend/', views.admin_suspend_player, name='admin_suspend_player'),
    path('admin/player/<int:player_id>/unsuspend/', views.admin_unsuspend_player, name='admin_unsuspend_player'),
    
    # Admin Officials Management
    path('admin/officials/', views.admin_manage_officials, name='admin_manage_officials'),
    path('admin/official/add/', views.admin_add_team_official, name='admin_add_official'),
    path('admin/official/<int:official_id>/suspend/', views.admin_suspend_official, name='admin_suspend_official'),
    path('admin/official/<int:official_id>/unsuspend/', views.admin_unsuspend_official, name='admin_unsuspend_official'),
    path('admin/official/<int:official_id>/delete/', views.admin_delete_official, name='admin_delete_team_official'),
    
]