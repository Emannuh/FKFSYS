from django.urls import path

from . import views

app_name = 'frontend'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('rules/', views.rules, name='rules'),
    path('styleguide/', views.styleguide, name='styleguide'),
]
