"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path

from admin_dashboard.views import dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    # Single role-aware dashboard entry point.
    path('dashboard/', login_required(dashboard), name='dashboard'),
    path('', include('frontend.urls')),
    path('teams/', include('teams.urls')),
    path('payments/', include('payments.urls')),
    path('matches/', include('matches.urls')),
    path('referees/', include('referees.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('admin-dashboard/', include('admin_dashboard.urls')),
    path('tournaments/', include('tournaments.urls')),
]

if settings.DEBUG:
    # Static files are served by django.contrib.staticfiles' runserver in DEBUG;
    # user uploads need an explicit route. In production both are served by the web server.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
