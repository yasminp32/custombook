from django.contrib import admin

from apps.banking.models import BankAccount, BankTransaction


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "account_type",
        "currency",
        "books_balance",
        "bank_balance",
        "is_primary",
        "status",
        "organization",
        "created_at",
    )
    list_filter = ("account_type", "status", "is_primary", "currency")
    search_fields = ("name", "account_code", "bank_name", "account_number", "ifsc_code")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "transaction_date",
        "transaction_type",
        "amount",
        "organization",
        "created_at",
    )
    list_filter = ("transaction_type", "transaction_date")
    search_fields = ("description", "reference_number", "account__name")
    readonly_fields = ("id", "created_at", "updated_at")
