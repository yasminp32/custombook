from django.db.models import Q
import django_filters

from apps.sales_orders.models import SalesOrder

SALES_ORDER_TAB_FILTERS = (
    ("all", "All"),
    ("draft", "Draft"),
    ("confirmed", "Confirmed"),
)

SALES_ORDER_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("draft", "DRAFT"),
    ("confirmed", "CONFIRMED"),
    ("invoiced", "INVOICED"),
    ("cancelled", "CANCELLED"),
)


class SalesOrderFilter(django_filters.FilterSet):
    sales_order_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    quote_id = django_filters.UUIDFilter(field_name="quote_id")
    sales_order_number = django_filters.CharFilter(lookup_expr="icontains")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(method="filter_status")
    order_date = django_filters.DateFilter()
    order_date_from = django_filters.DateFilter(field_name="order_date", lookup_expr="gte")
    order_date_to = django_filters.DateFilter(field_name="order_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = SalesOrder
        fields = (
            "sales_order_id",
            "id",
            "organization_id",
            "customer_id",
            "quote_id",
            "sales_order_number",
            "reference_number",
            "status",
            "order_date",
            "order_date_from",
            "order_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(sales_order_number__icontains=value)
            | Q(reference_number__icontains=value)
            | Q(subject__icontains=value)
            | Q(customer__display_name__icontains=value)
            | Q(customer__company_name__icontains=value)
            | Q(customer__first_name__icontains=value)
            | Q(customer__last_name__icontains=value)
            | Q(salesperson_name__icontains=value)
            | Q(project_name__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        status_value = (self.data.get("status") or "").strip().lower().replace(" ", "_")
        if status_value and status_value not in ("", "all", "all_statuses"):
            return queryset
        key = (value or "").strip().lower().replace(" ", "_")
        if key in ("draft", "confirmed"):
            return queryset.filter(status=key)
        return queryset

    def filter_status(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        if not key or key in ("all", "all_statuses"):
            return queryset
        allowed = {choice[0] for choice in SALES_ORDER_STATUS_FILTERS}
        if key not in allowed:
            return queryset.none()
        return queryset.filter(status=key)
