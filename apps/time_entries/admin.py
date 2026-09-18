from django.contrib import admin

from apps.time_entries.models import TimeEntry


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "task_name",
        "project",
        "user",
        "log_date",
        "hours",
        "minutes",
        "is_billable",
        "organization",
        "created_at",
    )
    list_filter = ("is_billable", "log_date")
    search_fields = (
        "task_name",
        "notes",
        "project__name",
        "user__email",
    )
    readonly_fields = ("id", "duration_minutes", "created_at", "updated_at")
