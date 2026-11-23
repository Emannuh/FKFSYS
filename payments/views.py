import json
import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from fkf_league.permissions import is_league_admin
from teams.models import Team

from . import services
from .daraja import callback_token
from .forms import PaymentForm
from .models import Payment

logger = logging.getLogger(__name__)

MAX_CALLBACK_BYTES = 16 * 1024


def _can_access_team_payment(request, team: Team) -> bool:
    """The registering browser session, the team's manager, or a league admin."""
    if request.session.get("team_id_for_payment") == team.pk:
        return True
    user = request.user
    return user.is_authenticated and (team.manager_id == user.pk or is_league_admin(user))


@require_http_methods(["GET", "POST"])
def payment_page(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    if not _can_access_team_payment(request, team):
        raise PermissionDenied
    if services.team_has_paid(team):
        messages.info(request, "This team has already completed payment.")
        return redirect("teams:registration_success")

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                payment = services.initiate_registration_payment(team, form.cleaned_data["phone_number"])
            except services.PaymentError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Payment request sent. Check your phone and enter your M-PESA PIN.")
                return redirect("payments:payment_status", payment_id=payment.pk)
    else:
        form = PaymentForm(initial={"phone_number": team.phone_number})

    return render(request, "payments/payment.html", {
        "form": form,
        "team": team,
        "amount": services.REGISTRATION_FEE,
    })


@require_http_methods(["GET"])
def payment_status(request, payment_id):
    payment = get_object_or_404(Payment.objects.select_related("team"), pk=payment_id)
    if not _can_access_team_payment(request, payment.team):
        raise PermissionDenied
    # Read-only towards the user: only asks Daraja for the authoritative result.
    services.refresh_payment_status(payment)
    return render(request, "payments/payment_status.html", {"payment": payment, "team": payment.team})


@csrf_exempt  # External server-to-server callback from Safaricom; verified below.
@require_POST
def payment_callback(request, token):
    if not constant_time_compare(token, callback_token()):
        logger.warning("M-Pesa callback with invalid token rejected")
        raise Http404
    allowed_ips = getattr(settings, "MPESA_CALLBACK_ALLOWED_IPS", None)
    if allowed_ips and request.META.get("REMOTE_ADDR") not in allowed_ips:
        logger.warning("M-Pesa callback from non-allow-listed address rejected")
        raise PermissionDenied
    if len(request.body) > MAX_CALLBACK_BYTES:
        return HttpResponseBadRequest("payload too large")
    try:
        payload = json.loads(request.body)
        outcome = services.process_stk_callback(payload)
    except (ValueError, services.CallbackRejected) as exc:
        logger.warning("M-Pesa callback rejected: %s", type(exc).__name__)
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Rejected"}, status=400)
    logger.info("M-Pesa callback processed: %s", outcome)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
