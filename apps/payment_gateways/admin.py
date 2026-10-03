from django.contrib import admin

from apps.payment_gateways.models import OrganizationPaymentGateway


@admin.register(OrganizationPaymentGateway)
class OrganizationPaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ("gateway_code", "is_setup", "organization", "updated_at")
    list_filter = ("gateway_code", "is_setup")
    search_fields = ("gateway_code", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")
