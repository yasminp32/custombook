from django.contrib import admin

from apps.currencies.models import Currency


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "decimal_places", "number_format", "organization")
    list_filter = ("number_format", "decimal_places")
    search_fields = ("code", "name", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")
