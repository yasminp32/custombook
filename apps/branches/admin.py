from django.contrib import admin

from apps.branches.models import Address, Branch


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("address_line1", "city", "state", "country", "postal_code", "created_at")
    search_fields = ("address_line1", "city", "state", "postal_code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_primary", "status", "created_at")
    list_filter = ("status", "is_primary")
    search_fields = ("name", "organization__name")
    readonly_fields = ("created_at", "updated_at")
