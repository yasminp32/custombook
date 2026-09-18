from django.contrib import admin

from apps.purchase_orders.models import PurchaseOrder


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "purchase_order_number",
        "vendor",
        "order_date",
        "amount",
        "status",
        "organization",
        "created_at",
    )
    list_filter = ("status", "order_date")
    search_fields = (
        "purchase_order_number",
        "reference_number",
        "vendor__display_name",
        "vendor__company_name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "issued_at",
        "billed_at",
        "cancelled_at",
    )
