from django.contrib import admin

from apps.sender_emails.models import SenderEmail, SenderEmailPreference


@admin.register(SenderEmailPreference)
class SenderEmailPreferenceAdmin(admin.ModelAdmin):
    list_display = ("organization", "delivery_method", "updated_at")
    list_filter = ("delivery_method",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SenderEmail)
class SenderEmailAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "is_primary", "organization", "updated_at")
    list_filter = ("is_primary",)
    search_fields = ("name", "email", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")
