from django.contrib import admin

from apps.bills.models import Bill


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        "bill_number",
        "vendor",
        "bill_date",
        "due_date",
        "amount",
        "status",
        "organization",
        "created_at",
    )
    list_filter = ("status", "bill_date")
    search_fields = (
        "bill_number",
        "vendor__display_name",
        "vendor__company_name",
    )
    readonly_fields = ("id", "created_at", "updated_at", "opened_at", "paid_at")
