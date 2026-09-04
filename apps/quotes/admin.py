from django.contrib import admin

from apps.quotes.models import Quote, QuoteLine


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 0
    readonly_fields = ("id",)


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = (
        "quote_number",
        "customer",
        "quote_date",
        "status",
        "total_amount",
        "organization",
        "created_at",
    )
    list_filter = ("status", "tax_type", "quote_date")
    search_fields = (
        "quote_number",
        "reference_number",
        "subject",
        "customer__display_name",
        "customer__company_name",
    )
    readonly_fields = ("id", "created_at", "updated_at", "sent_at")
    inlines = [QuoteLineInline]
