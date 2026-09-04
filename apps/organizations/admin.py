from django.contrib import admin

from apps.organizations.models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "industry",
        "country",
        "state",
        "currency",
        "is_gst_registered",
        "is_setup_complete",
        "owner",
        "created_at",
    )
    list_filter = ("country", "currency", "industry", "is_gst_registered", "is_setup_complete")
    search_fields = ("name", "owner__email", "gstin")
    readonly_fields = ("created_at", "updated_at")
