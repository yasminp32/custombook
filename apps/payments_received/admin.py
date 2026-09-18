from django.contrib import admin

from apps.payments_received.models import PaymentReceived, PaymentReceivedApplication


class PaymentReceivedApplicationInline(admin.TabularInline):
    model = PaymentReceivedApplication
    extra = 0
    readonly_fields = ("id", "created_at")


@admin.register(PaymentReceived)
class PaymentReceivedAdmin(admin.ModelAdmin):
    list_display = (
        "payment_number",
        "customer",
        "payment_date",
        "payment_mode",
        "amount",
        "amount_applied",
        "organization",
        "created_at",
    )
    list_filter = ("payment_mode", "payment_date")
    search_fields = (
        "payment_number",
        "reference_number",
        "customer__display_name",
        "customer__company_name",
    )
    readonly_fields = ("id", "created_at", "updated_at", "amount_applied")
    inlines = [PaymentReceivedApplicationInline]
