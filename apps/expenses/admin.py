from django.contrib import admin

from apps.expenses.models import Expense, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "organization", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "key")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "category",
        "vendor",
        "expense_date",
        "amount",
        "status",
        "organization",
        "created_at",
    )
    list_filter = ("status", "expense_date")
    search_fields = (
        "category__name",
        "vendor__display_name",
        "vendor__company_name",
        "reference_number",
    )
    readonly_fields = ("id", "created_at", "updated_at")
