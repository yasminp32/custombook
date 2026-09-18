from datetime import date

from django.db.models import Q
import django_filters

from apps.bills.models import Bill

BILL_TAB_FILTERS = (
    ("all", "All"),
    ("open", "Open"),
    ("overdue", "Overdue"),
    ("paid", "Paid"),
)

BILL_STATUS_FILTERS = (
    ("all_bills", "All Bills"),
    ("draft", "DRAFT"),
    ("open", "OPEN"),
    ("overdue", "OVERDUE"),
    ("paid", "PAID"),
    ("partially_paid", "PARTIALLY PAID"),
)


def overdue_q():
    return Q(status=Bill.Status.OPEN, due_date__lt=date.today())


class BillFilter(django_filters.FilterSet):
    bill_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    vendor_id = django_filters.UUIDFilter(field_name="vendor_id")
    purchase_order_id = django_filters.UUIDFilter(field_name="purchase_order_id")
    bill_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(method="filter_status")
    bill_date = django_filters.DateFilter()
    bill_date_from = django_filters.DateFilter(field_name="bill_date", lookup_expr="gte")
    bill_date_to = django_filters.DateFilter(field_name="bill_date", lookup_expr="lte")
    due_date = django_filters.DateFilter()
    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = Bill
        fields = (
            "bill_id",
            "id",
            "organization_id",
            "vendor_id",
            "purchase_order_id",
            "bill_number",
            "status",
            "bill_date",
            "bill_date_from",
            "bill_date_to",
            "due_date",
            "due_date_from",
            "due_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(bill_number__icontains=value)
            | Q(vendor__display_name__icontains=value)
            | Q(vendor__company_name__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        status_value = (self.data.get("status") or "").strip().lower().replace(" ", "_")
        if status_value and status_value not in ("", "all", "all_bills"):
            return queryset
        key = (value or "").strip().lower().replace(" ", "_")
        if key == "open":
            return queryset.filter(status=Bill.Status.OPEN).exclude(overdue_q())
        if key == "overdue":
            return queryset.filter(overdue_q())
        if key == "paid":
            return queryset.filter(status=Bill.Status.PAID)
        return queryset

    def filter_status(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        if not key or key in ("all", "all_bills"):
            return queryset
        if key == "overdue":
            return queryset.filter(overdue_q())
        allowed = {choice[0] for choice in BILL_STATUS_FILTERS}
        if key not in allowed:
            return queryset.none()
        if key == Bill.Status.OPEN:
            return queryset.filter(status=key).exclude(overdue_q())
        return queryset.filter(status=key)
