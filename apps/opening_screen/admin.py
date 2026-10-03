from django.contrib import admin

from apps.opening_screen.models import OpeningScreen


@admin.register(OpeningScreen)
class OpeningScreenAdmin(admin.ModelAdmin):
    list_display = ("user", "screen", "updated_at")
    list_filter = ("screen",)
    search_fields = ("user__email",)
    readonly_fields = ("id", "created_at", "updated_at")
