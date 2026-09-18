from django.contrib import admin

from apps.delivery_challans.models import DeliveryChallan, DeliveryChallanLine


class DeliveryChallanLineInline(admin.TabularInline):
    model = DeliveryChallanLine
    extra = 0
    readonly_fields = ("id",)


@admin.register(DeliveryChallan)
class DeliveryChallanAdmin(admin.ModelAdmin):
    list_display = (
        "challan_number",
        "customer",
        "challan_date",
        "challan_type",
        "status",
        "total_amount",
        "organization",
        "created_at",
    )
    list_filter = ("status", "challan_type", "challan_date")
    search_fields = (
        "challan_number",
        "reference_number",
        "customer__display_name",
        "customer__company_name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "delivered_at",
        "returned_at",
        "cancelled_at",
    )
    inlines = [DeliveryChallanLineInline]
