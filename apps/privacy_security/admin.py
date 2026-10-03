from django.contrib import admin

from apps.privacy_security.models import PrivacySecurity


@admin.register(PrivacySecurity)
class PrivacySecurityAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "enable_app_lock",
        "biometric_unlock",
        "lock_on_app_exit",
        "auto_lock_after",
        "hide_amounts_on_dashboard",
    )
    list_filter = ("enable_app_lock", "hide_amounts_on_dashboard", "auto_lock_after")
    search_fields = ("user__email",)
    readonly_fields = ("id", "created_at", "updated_at", "cache_cleared_at")
