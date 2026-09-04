from django.contrib import admin

from apps.audit_logs.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "action",
        "entity_type",
        "entity_id",
        "user",
        "organization",
        "occurred_at",
    )
    list_filter = ("action", "entity_type")
    search_fields = ("entity_type", "action", "user__email")
    readonly_fields = (
        "id",
        "organization",
        "user",
        "entity_type",
        "entity_id",
        "action",
        "old_values",
        "new_values",
        "occurred_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
