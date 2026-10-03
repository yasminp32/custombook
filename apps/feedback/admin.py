from django.contrib import admin

from apps.feedback.models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("subject", "rating", "category", "user", "organization", "created_at")
    list_filter = ("category", "rating")
    search_fields = ("subject", "message", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")
