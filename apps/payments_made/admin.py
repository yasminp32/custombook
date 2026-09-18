from django.contrib import admin

from apps.payments_made.models import PaymentMade


@admin.register(PaymentMade)
class PaymentMadeAdmin(admin.ModelAdmin):
    list_display = (
        "payment_number",
        "vendor",
        "payment_date",
        "payment_mode",
        "amount",
        "organization",
        "created_at",
    )
    list_filter = ("payment_mode", "payment_date")
    search_fields = (
        "payment_number",
        "reference_number",
        "vendor__display_name",
        "vendor__company_name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
