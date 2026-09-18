from django.contrib import admin

from apps.folders.models import Folder


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "created_by", "created_at")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")
