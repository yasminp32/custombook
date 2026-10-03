from django.contrib import admin

from apps.preferences.models import CustomField, MileageRate, Preference


@admin.register(Preference)
class PreferenceAdmin(admin.ModelAdmin):
    list_display = ("organization", "discount_type", "tax_type", "rounding", "updated_at")
    search_fields = ("organization__name",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ("label", "entity", "data_type", "is_mandatory", "is_active", "organization")
    list_filter = ("entity", "data_type", "is_active")
    search_fields = ("label", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MileageRate)
class MileageRateAdmin(admin.ModelAdmin):
    list_display = ("start_date", "rate", "organization", "created_at")
    search_fields = ("organization__name",)
    readonly_fields = ("id", "created_at", "updated_at")
