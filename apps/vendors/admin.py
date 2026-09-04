from django.contrib import admin

from apps.vendors.models import Vendor, VendorPayment


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "gstin",
        "organization",
        "payment_term",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("display_name", "gstin")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(VendorPayment)
class VendorPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "vendor",
        "organization",
        "payment_date",
        "amount",
        "created_at",
    )
    list_filter = ("payment_date",)
    search_fields = ("vendor__display_name",)
    readonly_fields = ("id", "created_at", "updated_at")
