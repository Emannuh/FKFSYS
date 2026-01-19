# matches/urls.py
from django.urls import path
from django.views.generic.base import RedirectView
from . import views
# matches/urls.py
from django.urls import path
from django.views.generic.base import RedirectView
from . import views

app_name = 'matches'

urlpatterns = [
    # Redirect /matches/105/ to /matches/match/105/ (MUST BE FIRST!)
    path('<int:match_id>/', 
         RedirectView.as_view(pattern_name='matches:match_details', permanent=True)),

     # New views for results, admin edit, league table edit, league manager reschedule
     path('results/', views.match_results, name='match_results'),
     path('admin/match/<int:match_id>/edit-result/', views.admin_edit_match_result, name='admin_edit_match_result'),
     path('admin/league-table/<int:table_id>/edit/', views.admin_edit_league_table, name='admin_edit_league_table'),
     path('manager/match/<int:match_id>/reschedule/', views.league_manager_reschedule, name='league_manager_reschedule'),
    
    # Admin match management
    path('admin/manage/', 
         __import__('matches.admin_views').admin_views.manage_matches,
         name='manage_matches'),
    path('admin/create/', 
         __import__('matches.admin_views').admin_views.create_match,
         name='create_match'),
    path('admin/<int:match_id>/edit/', 
         __import__('matches.admin_views').admin_views.edit_match,
         name='edit_match'),
    path('admin/<int:match_id>/delete/', 
         __import__('matches.admin_views').admin_views.delete_match,
         name='delete_match'),
    
    # All other match-related URLs
    path('tables/', views.league_tables, name='league_tables'),
    path('fixtures/', views.fixtures, name='fixtures'),
    path('match/<int:match_id>/', views.match_details, name='match_details'),
    # Admin-only reschedule view
    path('match/<int:match_id>/reschedule/',
         __import__('matches.admin_views').admin_views.reschedule_match,
         name='reschedule_match'),
    # Move match to another round
    path('admin/<int:match_id>/move-round/',
         __import__('matches.move_match_round_view').move_match_round_view.move_match_round,
         name='move_match_round'),
    path('top-scorers/', views.top_scorers, name='top_scorers'),
    path('team/<int:team_id>/fixtures/', views.team_fixtures, name='team_fixtures'),
    path('zone/<int:zone_id>/fixtures/', views.zone_fixtures, name='zone_fixtures'),
]