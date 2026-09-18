from datetime import date

from django.db.models import Q
import django_filters

from apps.invoices.models import Invoice

INVOICE_TAB_FILTERS = (
    ("all", "All"),
    ("draft", "Draft"),
    ("overdue", "Overdue"),
    ("paid", "Paid"),
)

INVOICE_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("draft", "DRAFT"),
    ("sent", "SENT"),
    ("paid", "PAID"),
    ("partially_paid", "PARTIALLY PAID"),
    ("overdue", "OVERDUE"),
    ("cancelled", "CANCELLED"),
)

OVERDUE_STORED_STATUSES = (
    Invoice.Status.SENT,
    Invoice.Status.PARTIALLY_PAID,
)


def overdue_q():
    return Q(status__in=OVERDUE_STORED_STATUSES, due_date__lt=date.today())


class InvoiceFilter(django_filters.FilterSet):
    invoice_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    sales_order_id = django_filters.UUIDFilter(field_name="sales_order_id")
    delivery_challan_id = django_filters.UUIDFilter(field_name="delivery_challan_id")
    invoice_number = django_filters.CharFilter(lookup_expr="icontains")
    order_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(method="filter_status")
    invoice_date = django_filters.DateFilter()
    invoice_date_from = django_filters.DateFilter(field_name="invoice_date", lookup_expr="gte")
    invoice_date_to = django_filters.DateFilter(field_name="invoice_date", lookup_expr="lte")
    due_date = django_filters.DateFilter()
    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    place_of_supply = django_filters.CharFilter(lookup_expr="iexact")
    payment_terms = django_filters.CharFilter(lookup_expr="iexact")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = Invoice
        fields = (
            "invoice_id",
            "id",
            "organization_id",
            "customer_id",
            "sales_order_id",
            "delivery_challan_id",
            "invoice_number",
            "order_number",
            "status",
            "invoice_date",
            "invoice_date_from",
            "invoice_date_to",
            "due_date",
            "due_date_from",
            "due_date_to",
            "place_of_supply",
            "payment_terms",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(invoice_number__icontains=value)
            | Q(order_number__icontains=value)
            | Q(subject__icontains=value)
            | Q(salesperson_name__icontains=value)
            | Q(customer__display_name__icontains=value)
            | Q(customer__company_name__icontains=value)
            | Q(customer__first_name__icontains=value)
            | Q(customer__last_name__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        status_value = (self.data.get("status") or "").strip().lower().replace(" ", "_")
        if status_value and status_value not in ("", "all", "all_statuses"):
            return queryset
        key = (value or "").strip().lower().replace(" ", "_")
        if key == "draft":
            return queryset.filter(status=Invoice.Status.DRAFT)
        if key == "paid":
            return queryset.filter(status=Invoice.Status.PAID)
        if key == "overdue":
            return queryset.filter(overdue_q())
        return queryset

    def filter_status(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        if not key or key in ("all", "all_statuses"):
            return queryset
        if key == "overdue":
            return queryset.filter(overdue_q())
        allowed = {choice[0] for choice in INVOICE_STATUS_FILTERS}
        if key not in allowed:
            return queryset.none()
        if key in (Invoice.Status.SENT, Invoice.Status.PARTIALLY_PAID):
            return queryset.filter(status=key).exclude(overdue_q())
        return queryset.filter(status=key)
