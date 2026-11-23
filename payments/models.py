from django.db import models
from django.db.models import Q

from fkf_league.validators import validate_kenya_phone
from teams.models import Team


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(
        max_length=13,
        validators=[validate_kenya_phone],
        help_text="Must be +254 followed by 9 digits (e.g., +254712345678)",
    )
    transaction_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.TextField(blank=True)

    class Meta:
        ordering = ["-transaction_date"]
        constraints = [
            # One Payment row per Daraja CheckoutRequestID - callbacks match on it.
            models.UniqueConstraint(
                fields=["checkout_request_id"],
                condition=~Q(checkout_request_id=""),
                name="payments_unique_checkout_request_id",
            ),
        ]

    def __str__(self):
        return f"{self.team.team_name} - KSh {self.amount}"

    @property
    def masked_phone(self) -> str:
        p = self.phone_number or ""
        return f"{p[:6]}****{p[-3:]}" if len(p) >= 10 else "****"
