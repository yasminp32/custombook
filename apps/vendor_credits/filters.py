from django.db.models import Q
import django_filters

from apps.vendor_credits.models import VendorCredit

VENDOR_CREDIT_TAB_FILTERS = (
    ("all", "All"),
    ("open", "Open"),
    ("closed", "Closed"),
)

VENDOR_CREDIT_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("draft", "DRAFT"),
    ("open", "OPEN"),
    ("closed", "CLOSED"),
    ("void", "VOID"),
)


def normalize_key(value):
    return (value or "").strip().lower().replace(" ", "_").rstrip(".")


class VendorCreditFilter(django_filters.FilterSet):
    vendor_credit_id = django_filters.UUIDFilter(field_name="id")
    credit_note_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    vendor_id = django_filters.UUIDFilter(field_name="vendor_id")
    credit_note_number = django_filters.CharFilter(lookup_expr="icontains")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(method="filter_status")
    credit_date = django_filters.DateFilter()
    credit_date_from = django_filters.DateFilter(field_name="credit_date", lookup_expr="gte")
    credit_date_to = django_filters.DateFilter(field_name="credit_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = VendorCredit
        fields = (
            "vendor_credit_id",
            "credit_note_id",
            "id",
            "organization_id",
            "vendor_id",
            "credit_note_number",
            "reference_number",
            "status",
            "credit_date",
            "credit_date_from",
            "credit_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(credit_note_number__icontains=value)
            | Q(reference_number__icontains=value)
            | Q(vendor__display_name__icontains=value)
            | Q(vendor__company_name__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        status_value = normalize_key(self.data.get("status"))
        if status_value and status_value not in ("", "all", "all_statuses"):
            return queryset
        key = normalize_key(value)
        if key in ("open", "closed"):
            return queryset.filter(status=key)
        return queryset

    def filter_status(self, queryset, name, value):
        key = normalize_key(value)
        if not key or key in ("all", "all_statuses"):
            return queryset
        allowed = {choice[0] for choice in VENDOR_CREDIT_STATUS_FILTERS}
        if key not in allowed:
            return queryset.none()
        return queryset.filter(status=key)
