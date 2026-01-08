from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from admin_dashboard.views import dashboard  # Import your dashboard view

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Dashboard - ONE dashboard entry point
    path('dashboard/', login_required(dashboard), name='dashboard'),
    
    # App URLs
    path('', include('frontend.urls')),
    path('teams/', include('teams.urls')),
    path('payments/', include('payments.urls')),
    path('matches/', include('matches.urls')),
    path('referees/', include('referees.urls')),
    
    # Authentication
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Admin dashboard URLs (if you need specific admin views)
    path('admin-dashboard/', include('admin_dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)