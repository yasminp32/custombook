from django.contrib import admin

from apps.sales_orders.models import SalesOrder, SalesOrderLine


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 0
    readonly_fields = ("id",)


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = (
        "sales_order_number",
        "customer",
        "order_date",
        "status",
        "total_amount",
        "organization",
        "created_at",
    )
    list_filter = ("status", "tax_type", "order_date")
    search_fields = (
        "sales_order_number",
        "reference_number",
        "subject",
        "customer__display_name",
        "customer__company_name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "confirmed_at",
        "invoiced_at",
        "cancelled_at",
    )
    inlines = [SalesOrderLineInline]
