from django.urls import path
from django.views.generic.base import RedirectView

from . import admin_views, views

app_name = 'matches'

urlpatterns = [
    # Legacy short URL /matches/<id>/ -> /matches/match/<id>/
    path('<int:match_id>/', RedirectView.as_view(pattern_name='matches:match_details', permanent=True)),

    # Public
    path('results/', views.match_results, name='match_results'),
    path('tables/', views.league_tables, name='league_tables'),
    path('fixtures/', views.fixtures, name='fixtures'),
    path('top-scorers/', views.top_scorers, name='top_scorers'),
    path('team/<int:team_id>/fixtures/', views.team_fixtures, name='team_fixtures'),
    path('zone/<int:zone_id>/fixtures/', views.zone_fixtures, name='zone_fixtures'),
    path('match/<int:match_id>/', views.match_details, name='match_details'),
    path('match/<int:match_id>/officials/', views.view_match_officials, name='view_match_officials'),

    # League admin
    path('admin/match/<int:match_id>/edit-result/', views.admin_edit_match_result, name='admin_edit_match_result'),
    path('admin/league-table/<int:table_id>/edit/', views.admin_edit_league_table, name='admin_edit_league_table'),

    # Staff match management
    path('admin/manage/', admin_views.manage_matches, name='manage_matches'),
    path('admin/create/', admin_views.create_match, name='create_match'),
    path('admin/<int:match_id>/edit/', admin_views.edit_match, name='edit_match'),
    path('admin/<int:match_id>/delete/', admin_views.delete_match, name='delete_match'),
    path('admin/<int:match_id>/move-round/', admin_views.move_match_round, name='move_match_round'),
    path('match/<int:match_id>/reschedule/', admin_views.reschedule_match, name='reschedule_match'),
]
