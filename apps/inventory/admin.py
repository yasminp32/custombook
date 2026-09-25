from django.contrib import admin

from apps.inventory.models import (
    InventoryAdjustment,
    InventoryAdjustmentActivity,
    InventoryAdjustmentLine,
)


class InventoryAdjustmentLineInline(admin.TabularInline):
    model = InventoryAdjustmentLine
    extra = 0
    readonly_fields = ("id",)


class InventoryAdjustmentActivityInline(admin.TabularInline):
    model = InventoryAdjustmentActivity
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        "reason",
        "date",
        "adjustment_type",
        "status",
        "quantity_change",
        "adjustment_value",
        "adjusted_by_name",
        "organization",
        "created_at",
    )
    list_filter = ("adjustment_type", "status")
    search_fields = ("reason", "adjusted_by_name", "reference_number")
    readonly_fields = ("id", "quantity_change", "adjustment_value", "stock_applied", "created_at", "updated_at")
    inlines = [InventoryAdjustmentLineInline, InventoryAdjustmentActivityInline]
