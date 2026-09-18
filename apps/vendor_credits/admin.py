from django.contrib import admin

from apps.vendor_credits.models import VendorCredit


@admin.register(VendorCredit)
class VendorCreditAdmin(admin.ModelAdmin):
    list_display = (
        "credit_note_number",
        "vendor",
        "credit_date",
        "amount",
        "status",
        "organization",
        "created_at",
    )
    list_filter = ("status", "credit_date")
    search_fields = (
        "credit_note_number",
        "reference_number",
        "vendor__display_name",
        "vendor__company_name",
    )
    readonly_fields = ("id", "created_at", "updated_at", "closed_at", "voided_at")
