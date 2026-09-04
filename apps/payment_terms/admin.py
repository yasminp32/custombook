from django.contrib import admin

from apps.payment_terms.models import PaymentTerm


@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    list_display = ("name", "due_days", "is_default", "organization", "created_at")
    list_filter = ("is_default",)
    search_fields = ("name", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")
