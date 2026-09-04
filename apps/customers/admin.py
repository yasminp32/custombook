from django.contrib import admin

from apps.customers.models import (
    Customer,
    CustomerAddress,
    CustomerContactPerson,
    CustomerPayment,
    CustomerSocialLink,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "company_name",
        "email",
        "customer_type",
        "tax_treatment",
        "receivables",
        "unused_credits",
        "organization",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "customer_type",
        "tax_treatment",
        "synced_with_crm",
        "portal_enabled",
        "is_overdue",
    )
    search_fields = (
        "display_name",
        "company_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "mobile",
        "gstin",
    )
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ("customer", "address", "address_type")
    list_filter = ("address_type",)
    search_fields = ("customer__display_name", "customer__company_name", "address__city")
    readonly_fields = ("id",)


@admin.register(CustomerContactPerson)
class CustomerContactPersonAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "customer",
        "designation",
        "department",
    )
    search_fields = ("first_name", "last_name", "email", "customer__display_name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CustomerSocialLink)
class CustomerSocialLinkAdmin(admin.ModelAdmin):
    list_display = ("platform", "url", "customer")
    list_filter = ("platform",)
    search_fields = ("url", "customer__display_name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_number",
        "customer",
        "organization",
        "payment_date",
        "amount",
        "created_at",
    )
    list_filter = ("payment_date",)
    search_fields = ("payment_number", "reference_number", "customer__display_name")
    readonly_fields = ("id", "created_at", "updated_at")
