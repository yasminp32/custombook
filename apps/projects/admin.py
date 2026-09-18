from django.contrib import admin

from apps.projects.models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "customer",
        "billing_method",
        "rate",
        "status",
        "organization",
        "created_at",
    )
    list_filter = ("status", "billing_method")
    search_fields = (
        "name",
        "customer__display_name",
        "customer__company_name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "completed_at",
        "cancelled_at",
        "on_hold_at",
    )
