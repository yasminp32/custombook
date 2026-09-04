from django.contrib import admin

from apps.users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("email", "full_name")
    readonly_fields = ("id", "created_at", "updated_at")
