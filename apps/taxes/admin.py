from django.contrib import admin

from apps.taxes.models import TaxRate, TaxSettings


@admin.register(TaxSettings)
class TaxSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "is_vat_registered",
        "tax_registration_number",
        "reporting_period",
        "profit_margin_scheme",
    )
    list_filter = ("is_vat_registered", "reporting_period", "profit_margin_scheme")
    search_fields = ("organization__name", "tax_registration_number")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ("name", "rate", "tax_type", "is_default", "organization")
    list_filter = ("tax_type", "is_default")
    search_fields = ("name", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")
