from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Read-only audit view of M-Pesa payments. Records change only via Daraja."""

    list_display = ["team", "amount", "status", "mpesa_receipt_number", "masked_phone", "transaction_date"]
    list_filter = ["status"]
    search_fields = ["team__team_name", "mpesa_receipt_number", "checkout_request_id"]
    list_select_related = ["team"]
    date_hierarchy = "transaction_date"
    exclude = ["phone_number"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields if f.name != "phone_number"] + ["masked_phone"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Phone")
    def masked_phone(self, obj):
        return obj.masked_phone
