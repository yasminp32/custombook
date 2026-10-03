from django.contrib import admin

from apps.pdf_templates.models import PdfTemplate


@admin.register(PdfTemplate)
class PdfTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "document_type",
        "theme",
        "is_default",
        "is_system",
        "organization",
    )
    list_filter = ("document_type", "theme", "is_default", "is_system")
    search_fields = ("name", "organization__name", "bank_name", "signatory_name")
    readonly_fields = ("id", "created_at", "updated_at")
