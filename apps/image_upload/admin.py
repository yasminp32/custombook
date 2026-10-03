from django.contrib import admin

from apps.image_upload.models import ImageUploadResolution


@admin.register(ImageUploadResolution)
class ImageUploadResolutionAdmin(admin.ModelAdmin):
    list_display = ("user", "resolution", "updated_at")
    list_filter = ("resolution",)
    search_fields = ("user__email",)
    readonly_fields = ("id", "created_at", "updated_at")
