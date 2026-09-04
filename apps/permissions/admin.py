from django.contrib import admin

from apps.permissions.models import RolePermission


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "module", "permission_level")
    list_filter = ("permission_level", "module")
    search_fields = ("role__role_name", "role__role_code", "module")
    readonly_fields = ("id",)
