from django.contrib import admin

from apps.manual_journals.models import ManualJournal


@admin.register(ManualJournal)
class ManualJournalAdmin(admin.ModelAdmin):
    list_display = (
        "journal_number",
        "reference_number",
        "journal_date",
        "amount",
        "status",
        "organization",
        "created_at",
    )
    list_filter = ("status", "journal_date")
    search_fields = ("journal_number", "reference_number", "notes")
    readonly_fields = ("id", "created_at", "updated_at", "published_at")
