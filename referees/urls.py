# referees/urls.py
from django.urls import path
from . import views

app_name = 'referees'  # Add this line

urlpatterns = [
    path('dashboard/', views.referee_dashboard, name='referee_dashboard'),
    path('register/', views.referee_registration, name='referee_registration'),
    path('matches/', views.referee_matches, name='referee_matches'),
    path('report/<int:match_id>/', views.submit_match_report, name='submit_match_report'),
    path('view-report/<int:report_id>/', views.view_report, name='view_report'),
]