from django.db.models import Q
import django_filters

from apps.delivery_challans.models import DeliveryChallan

CHALLAN_TAB_FILTERS = (
    ("all", "All"),
    ("draft", "Draft"),
    ("delivered", "Delivered"),
)

CHALLAN_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("draft", "DRAFT"),
    ("delivered", "DELIVERED"),
    ("returned", "RETURNED"),
    ("cancelled", "CANCELLED"),
)


class DeliveryChallanFilter(django_filters.FilterSet):
    delivery_challan_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    sales_order_id = django_filters.UUIDFilter(field_name="sales_order_id")
    challan_number = django_filters.CharFilter(lookup_expr="icontains")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")
    challan_type = django_filters.CharFilter(method="filter_challan_type")
    status = django_filters.CharFilter(method="filter_status")
    challan_date = django_filters.DateFilter()
    challan_date_from = django_filters.DateFilter(field_name="challan_date", lookup_expr="gte")
    challan_date_to = django_filters.DateFilter(field_name="challan_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = DeliveryChallan
        fields = (
            "delivery_challan_id",
            "id",
            "organization_id",
            "customer_id",
            "sales_order_id",
            "challan_number",
            "reference_number",
            "challan_type",
            "status",
            "challan_date",
            "challan_date_from",
            "challan_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(challan_number__icontains=value)
            | Q(reference_number__icontains=value)
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
        if key in ("draft", "delivered"):
            return queryset.filter(status=key)
        return queryset

    def filter_status(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        if not key or key in ("all", "all_statuses"):
            return queryset
        allowed = {choice[0] for choice in CHALLAN_STATUS_FILTERS}
        if key not in allowed:
            return queryset.none()
        return queryset.filter(status=key)

    def filter_challan_type(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        if not key:
            return queryset
        aliases = {
            "job_work": "job_work",
            "jobwork": "job_work",
            "supply_on_approval": "supply_on_approval",
            "supply_of_liquid_gas": "supply_of_liquid_gas",
            "others": "others",
            "other": "others",
        }
        mapped = aliases.get(key)
        if not mapped:
            return queryset.none()
        return queryset.filter(challan_type=mapped)
