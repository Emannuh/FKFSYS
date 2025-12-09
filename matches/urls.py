# matches/urls.py
from django.urls import path
from . import views

app_name = 'matches'  # Add this line

urlpatterns = [
    path('tables/', views.league_tables, name='league_tables'),
    path('fixtures/', views.fixtures, name='fixtures'),
    path('match/<int:match_id>/', views.match_details, name='match_details'),
    path('top-scorers/', views.top_scorers, name='top_scorers'),
    path('team/<int:team_id>/fixtures/', views.team_fixtures, name='team_fixtures'),
    path('zone/<int:zone_id>/fixtures/', views.zone_fixtures, name='zone_fixtures'),
]