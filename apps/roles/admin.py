from django.contrib import admin

from apps.roles.models import Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("role_name", "role_code", "is_system_role", "created_at")
    list_filter = ("is_system_role",)
    search_fields = ("role_name", "role_code")
    readonly_fields = ("id", "created_at", "updated_at")
