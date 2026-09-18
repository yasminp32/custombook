from django.contrib import admin

from apps.credit_notes.models import CreditNote


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = (
        "credit_note_number",
        "customer",
        "credit_note_date",
        "amount",
        "status",
        "organization",
        "created_at",
    )
    list_filter = ("status", "credit_note_date")
    search_fields = (
        "credit_note_number",
        "reference_number",
        "customer__display_name",
        "customer__company_name",
    )
    readonly_fields = ("id", "created_at", "updated_at", "closed_at", "voided_at")
