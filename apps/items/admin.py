from django.contrib import admin

from apps.items.models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "item_type",
        "status",
        "selling_price",
        "cost_price",
        "organization",
        "created_at",
    )
    list_filter = ("item_type", "status", "sales_enabled", "purchase_enabled", "track_inventory")
    search_fields = ("name", "sku")
    readonly_fields = ("id", "created_at", "updated_at")
