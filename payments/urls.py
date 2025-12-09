# payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'  # Add this line

urlpatterns = [
    path('pay/<int:team_id>/', views.payment_page, name='payment_page'),
    path('status/<int:payment_id>/', views.payment_status, name='payment_status'),
    path('callback/', views.payment_callback, name='payment_callback'),
]