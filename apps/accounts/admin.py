from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import EmailOTP, PasswordResetToken, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "user_type",
        "phone",
        "is_email_verified",
        "is_staff",
        "created_at",
    )
    list_filter = ("user_type", "is_email_verified", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("-created_at",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "user_type", "phone_country_code", "phone")},
        ),
        ("Status", {"fields": ("is_email_verified", "terms_accepted_at")}),
        (
            "Security",
            {"fields": ("failed_login_attempts", "locked_until")},
        ),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "is_used", "expires_at", "created_at")
    list_filter = ("is_used",)
    search_fields = ("user__email", "code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "otp", "is_used", "expires_at", "used_at", "created_at")
    list_filter = ("is_used",)
    search_fields = ("user__email", "otp")
    readonly_fields = ("created_at",)
