from django.contrib import admin

from apps.inbox.models import InboxDocument


@admin.register(InboxDocument)
class InboxDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "file_type",
        "file_size",
        "folder",
        "organization",
        "created_at",
    )
    list_filter = ("file_type", "folder")
    search_fields = ("name", "mime_type")
    readonly_fields = ("id", "storage_key", "share_token", "created_at", "updated_at")
