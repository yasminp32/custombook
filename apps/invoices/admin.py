from django.contrib import admin

from apps.invoices.models import Invoice, InvoiceLine


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    readonly_fields = ("id",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "customer",
        "invoice_date",
        "due_date",
        "status",
        "total_amount",
        "organization",
        "created_at",
    )
    list_filter = ("status", "invoice_date", "payment_terms")
    search_fields = (
        "invoice_number",
        "order_number",
        "customer__display_name",
        "customer__company_name",
        "salesperson_name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "sent_at",
        "paid_at",
        "cancelled_at",
    )
    inlines = [InvoiceLineInline]
