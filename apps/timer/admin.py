from django.contrib import admin

from apps.timer.models import TimerSession


@admin.register(TimerSession)
class TimerSessionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "project",
        "task_name",
        "status",
        "accumulated_seconds",
        "organization",
        "updated_at",
    )
    list_filter = ("status",)
    search_fields = ("task_name", "notes", "project__name", "user__email")
    readonly_fields = ("id", "started_at", "created_at", "updated_at")
