from django.contrib import admin

from apps.recurring_invoices.models import RecurringInvoice, RecurringInvoiceActivity


class RecurringInvoiceActivityInline(admin.TabularInline):
    model = RecurringInvoiceActivity
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(RecurringInvoice)
class RecurringInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "profile_name",
        "customer",
        "frequency",
        "start_date",
        "amount",
        "status",
        "organization",
        "created_at",
    )
    list_filter = ("status", "frequency", "start_date")
    search_fields = (
        "profile_name",
        "customer__display_name",
        "customer__company_name",
    )
    readonly_fields = ("id", "created_at", "updated_at", "stopped_at")
    inlines = [RecurringInvoiceActivityInline]
