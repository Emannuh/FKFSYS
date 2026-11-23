"""
Payment business logic: starting a registration payment and settling it from
the Daraja callback or the Daraja status query.

Invariants:
- A Payment is only ever marked completed from data Safaricom sent us
  server-to-server (callback with a valid URL token, cross-checked against a
  pending Payment we created, *and* confirmed by the STK status query), or from
  the STK status query alone. Nothing from the browser can complete a payment.
- Settlement is idempotent: only ``pending`` payments transition, under a row
  lock, so duplicate callbacks/polls cannot double-apply.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from teams.models import Team

from .daraja import DarajaClient, DarajaError, mask_phone
from .models import Payment

logger = logging.getLogger(__name__)

REGISTRATION_FEE = Decimal("16000")
# Don't send another STK push for the same team while one is fresh.
STK_RESEND_COOLDOWN = timedelta(minutes=2)


class PaymentError(Exception):
    """User-facing failure to start a payment (message is safe to display)."""


# ── Initiation ──────────────────────────────────────────────────────────────

def team_has_paid(team: Team) -> bool:
    return team.payment_status or team.payments.filter(status=Payment.Status.COMPLETED).exists()


def initiate_registration_payment(team: Team, phone: str, client: DarajaClient | None = None) -> Payment:
    """Send an STK push for the registration fee and record a pending Payment."""
    if team_has_paid(team):
        raise PaymentError("This team has already completed payment.")
    recent = team.payments.filter(
        status=Payment.Status.PENDING,
        transaction_date__gte=timezone.now() - STK_RESEND_COOLDOWN,
    ).exists()
    if recent:
        raise PaymentError("A payment request was sent moments ago. Check your phone or wait two minutes.")

    try:
        client = client or DarajaClient()
        response = client.stk_push(
            phone=phone,
            amount=int(REGISTRATION_FEE),
            account_reference=team.team_code,
            description="FKF Reg Fee",
        )
    except DarajaError as exc:
        logger.warning("Payment initiation failed for team %s: %s", team.pk, type(exc).__name__)
        raise PaymentError("Could not start the M-PESA payment. Please try again shortly.") from exc

    payment = Payment.objects.create(
        team=team,
        amount=REGISTRATION_FEE,
        phone_number=phone,
        checkout_request_id=response["CheckoutRequestID"],
        merchant_request_id=response.get("MerchantRequestID", ""),
        status=Payment.Status.PENDING,
    )
    logger.info("Payment %s pending for team %s (phone %s)", payment.pk, team.pk, mask_phone(phone))
    return payment


# ── Settlement ──────────────────────────────────────────────────────────────

def _settle(payment_id: int, *, success: bool, result_code: int | None, result_desc: str,
            receipt: str = "") -> bool:
    """Atomically move a *pending* payment to completed/failed. Returns True if it transitioned."""
    with transaction.atomic():
        payment = Payment.objects.select_for_update().select_related("team").get(pk=payment_id)
        if payment.status != Payment.Status.PENDING:
            return False
        payment.result_code = result_code
        payment.result_desc = (result_desc or "")[:500]
        if receipt:
            payment.mpesa_receipt_number = receipt[:50]
        payment.status = Payment.Status.COMPLETED if success else Payment.Status.FAILED
        payment.save(update_fields=["status", "result_code", "result_desc", "mpesa_receipt_number"])
        if success:
            Team.objects.filter(pk=payment.team_id).update(
                payment_status=True, payment_date=timezone.localdate(),
            )
    logger.info("Payment %s settled: %s (code=%s)", payment_id, payment.status, result_code)
    return True


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _query_result_code(payment: Payment, client: DarajaClient | None) -> int | None:
    """Authoritative ResultCode from Daraja, or None if not (yet) available."""
    try:
        data = (client or DarajaClient()).query_status(payment.checkout_request_id)
    except DarajaError:
        return None
    return _as_int(data.get("ResultCode"))


def refresh_payment_status(payment: Payment, client: DarajaClient | None = None) -> Payment:
    """Poll Daraja for a pending payment and settle it if a final result is known."""
    if payment.status != Payment.Status.PENDING or not payment.checkout_request_id:
        return payment
    code = _query_result_code(payment, client)
    if code is not None:
        _settle(payment.pk, success=(code == 0), result_code=code,
                result_desc="Confirmed by M-Pesa status query")
        payment.refresh_from_db()
    return payment


class CallbackRejected(Exception):
    """Callback payload is malformed (respond 400)."""


def _parse_callback(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CallbackRejected("payload is not an object")
    body = payload.get("Body")
    cb = body.get("stkCallback") if isinstance(body, dict) else None
    if not isinstance(cb, dict):
        raise CallbackRejected("missing Body.stkCallback")
    checkout_id = cb.get("CheckoutRequestID")
    merchant_id = cb.get("MerchantRequestID")
    result_code = _as_int(cb.get("ResultCode"))
    if not isinstance(checkout_id, str) or not checkout_id or len(checkout_id) > 100:
        raise CallbackRejected("bad CheckoutRequestID")
    if not isinstance(merchant_id, str) or len(merchant_id) > 100:
        raise CallbackRejected("bad MerchantRequestID")
    if result_code is None:
        raise CallbackRejected("bad ResultCode")

    items: dict[str, Any] = {}
    meta = cb.get("CallbackMetadata")
    if isinstance(meta, dict) and isinstance(meta.get("Item"), list):
        for item in meta["Item"]:
            if isinstance(item, dict) and isinstance(item.get("Name"), str):
                items[item["Name"]] = item.get("Value")
    return {
        "checkout_id": checkout_id,
        "merchant_id": merchant_id,
        "result_code": result_code,
        "result_desc": str(cb.get("ResultDesc") or "")[:500],
        "items": items,
    }


def process_stk_callback(payload: Any, client: DarajaClient | None = None) -> str:
    """
    Handle a Daraja STK callback. Returns an outcome label (for logs/tests):
    ``unknown``, ``duplicate``, ``failed``, ``completed``, ``rejected``, ``unverified``.
    Raises CallbackRejected for malformed payloads.
    """
    data = _parse_callback(payload)
    payment = Payment.objects.filter(checkout_request_id=data["checkout_id"]).first()
    if payment is None:
        logger.warning("M-Pesa callback for unknown CheckoutRequestID ignored")
        return "unknown"
    if payment.merchant_request_id and data["merchant_id"] != payment.merchant_request_id:
        logger.warning("M-Pesa callback MerchantRequestID mismatch for payment %s", payment.pk)
        return "rejected"
    if payment.status != Payment.Status.PENDING:
        return "duplicate"

    if data["result_code"] != 0:
        settled = _settle(payment.pk, success=False, result_code=data["result_code"],
                          result_desc=data["result_desc"])
        return "failed" if settled else "duplicate"

    items = data["items"]
    receipt = items.get("MpesaReceiptNumber")
    try:
        paid_amount = Decimal(str(items.get("Amount")))
    except (InvalidOperation, ValueError):
        paid_amount = None
    if not isinstance(receipt, str) or not receipt or paid_amount != payment.amount:
        logger.error(
            "M-Pesa callback verification failed for payment %s (amount match=%s, receipt present=%s)",
            payment.pk, paid_amount == payment.amount, bool(receipt),
        )
        Payment.objects.filter(pk=payment.pk, status=Payment.Status.PENDING).update(
            result_desc="Callback failed verification - needs manual reconciliation",
            mpesa_receipt_number=str(receipt or "")[:50],
        )
        return "rejected"

    # Defence in depth: confirm with Daraja server-to-server before completing.
    code = _query_result_code(payment, client)
    if code != 0:
        # Keep the receipt; leave pending so the status poll can settle it later.
        Payment.objects.filter(pk=payment.pk, status=Payment.Status.PENDING).update(
            mpesa_receipt_number=receipt[:50],
        )
        logger.warning("M-Pesa callback for payment %s not confirmed by status query (code=%s)",
                       payment.pk, code)
        if code is not None:
            _settle(payment.pk, success=False, result_code=code,
                    result_desc="Status query did not confirm payment")
            return "failed"
        return "unverified"

    settled = _settle(payment.pk, success=True, result_code=0,
                      result_desc=data["result_desc"], receipt=receipt)
    return "completed" if settled else "duplicate"
