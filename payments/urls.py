from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("pay/<int:team_id>/", views.payment_page, name="payment_page"),
    path("status/<int:payment_id>/", views.payment_status, name="payment_status"),
    # Called by Safaricom only. The token is an HMAC of SECRET_KEY (see daraja.callback_token).
    path("callback/<str:token>/", views.payment_callback, name="payment_callback"),
]
