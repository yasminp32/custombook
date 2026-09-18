from django.db.models import Q
import django_filters

from apps.expenses.models import Expense

EXPENSE_TAB_FILTERS = (
    ("all", "All"),
    ("unbilled", "Unbilled"),
    ("billed", "Billed"),
)

EXPENSE_STATUS_FILTERS = (
    ("all_expenses", "ALL EXPENSES"),
    ("unbilled", "UNBILLED"),
    ("billed", "BILLED"),
    ("reimbursed", "REIMBURSED"),
    ("non_billable", "NON-BILLABLE"),
)


class ExpenseFilter(django_filters.FilterSet):
    expense_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    category_id = django_filters.UUIDFilter(field_name="category_id")
    vendor_id = django_filters.UUIDFilter(field_name="vendor_id")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(method="filter_status")
    expense_date = django_filters.DateFilter()
    expense_date_from = django_filters.DateFilter(
        field_name="expense_date",
        lookup_expr="gte",
    )
    expense_date_to = django_filters.DateFilter(
        field_name="expense_date",
        lookup_expr="lte",
    )
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = Expense
        fields = (
            "expense_id",
            "id",
            "organization_id",
            "category_id",
            "vendor_id",
            "reference_number",
            "status",
            "expense_date",
            "expense_date_from",
            "expense_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(category__name__icontains=value)
            | Q(vendor__display_name__icontains=value)
            | Q(vendor__company_name__icontains=value)
            | Q(reference_number__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        status_value = (self.data.get("status") or "").strip().lower().replace(" ", "_")
        if status_value and status_value not in ("", "all", "all_expenses"):
            return queryset
        key = (value or "").strip().lower().replace(" ", "_")
        if key in ("unbilled", "billed"):
            return queryset.filter(status=key)
        return queryset

    def filter_status(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
        if not key or key in ("all", "all_expenses"):
            return queryset
        if key not in Expense.Status.values:
            return queryset.none()
        return queryset.filter(status=key)
