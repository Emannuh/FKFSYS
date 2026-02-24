from django.urls import path
from . import views

app_name = 'tournaments'

urlpatterns = [
    # ── Public ────────────────────────────────────────────────────────────
    path('', views.tournament_list, name='tournament_list'),
    path('<slug:slug>/', views.tournament_detail, name='tournament_detail'),
    path('<slug:slug>/fixtures/', views.tournament_fixtures, name='tournament_fixtures'),
    path('<slug:slug>/standings/', views.tournament_standings, name='tournament_standings'),

    # ── League team manager actions ───────────────────────────────────────
    path('<slug:slug>/register/', views.register_team, name='register_team'),
    path('<slug:slug>/register-players/', views.register_players, name='register_players'),

    # ── External team registration (public portal) ───────────────────────
    path('<slug:slug>/register-external/', views.register_external_team, name='register_external_team'),
    path('<slug:slug>/external-team/<int:ext_team_pk>/players/',
         views.register_external_players, name='register_external_players'),

    # ── Admin CRUD ────────────────────────────────────────────────────────
    path('admin/dashboard/', views.admin_tournament_dashboard, name='admin_dashboard'),
    path('admin/create/', views.create_tournament, name='create_tournament'),
    path('<slug:slug>/edit/', views.edit_tournament, name='edit_tournament'),
    path('<slug:slug>/delete/', views.delete_tournament, name='delete_tournament'),
    path('<slug:slug>/status/', views.change_tournament_status, name='change_status'),

    # ── Admin: import league teams ────────────────────────────────────────
    path('<slug:slug>/import-teams/', views.import_league_teams, name='import_league_teams'),

    # ── Admin registration management ────────────────────────────────────
    path('<slug:slug>/registrations/', views.manage_registrations, name='manage_registrations'),
    path('registration/<int:pk>/review/', views.review_registration, name='review_registration'),

    # ── Admin match management ────────────────────────────────────────────
    path('<slug:slug>/matches/create/', views.create_match, name='create_match'),
    path('match/<int:match_pk>/result/', views.record_result, name='record_result'),

    # ── Admin: fixture generation ─────────────────────────────────────────
    path('<slug:slug>/generate-fixtures/', views.generate_fixtures, name='generate_fixtures'),

    # ── Admin: officials appointment ──────────────────────────────────────
    path('match/<int:match_pk>/officials/', views.appoint_officials, name='appoint_officials'),
    path('<slug:slug>/matches-needing-officials/', views.matches_needing_officials,
         name='matches_needing_officials'),
]
