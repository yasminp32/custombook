from django.contrib import admin

from apps.attachments.models import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "file_name",
        "attachable_type",
        "attachable_id",
        "organization",
        "mime_type",
        "file_size",
        "created_at",
    )
    list_filter = ("attachable_type", "mime_type")
    search_fields = ("file_name", "storage_key", "attachable_type")
    readonly_fields = ("id", "created_at", "updated_at")
