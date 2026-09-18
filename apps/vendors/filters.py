from django.db.models import Q
import django_filters

from apps.vendors.models import Vendor

VENDOR_TAB_FILTERS = (
    ("all", "All"),
    ("active", "Active"),
    ("inactive", "Inactive"),
)

VENDOR_STATUS_FILTERS = (
    ("all_vendors", "All Vendors"),
    ("active", "ACTIVE"),
    ("inactive", "INACTIVE"),
)


class VendorFilter(django_filters.FilterSet):
    vendor_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    display_name = django_filters.CharFilter(lookup_expr="icontains")
    company_name = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="icontains")
    phone = django_filters.CharFilter(lookup_expr="icontains")
    gstin = django_filters.CharFilter(lookup_expr="icontains")
    payment_term_id = django_filters.UUIDFilter(field_name="payment_term_id")
    status = django_filters.CharFilter(method="filter_status")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = Vendor
        fields = (
            "vendor_id",
            "id",
            "organization_id",
            "display_name",
            "company_name",
            "email",
            "phone",
            "gstin",
            "payment_term_id",
            "status",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(display_name__icontains=value)
            | Q(company_name__icontains=value)
            | Q(email__icontains=value)
            | Q(phone__icontains=value)
            | Q(gstin__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        status_value = (self.data.get("status") or "").strip().lower().replace(" ", "_")
        if status_value and status_value not in ("", "all", "all_vendors"):
            return queryset
        key = (value or "").strip().lower().replace(" ", "_")
        if key in ("active", "inactive"):
            return queryset.filter(status=key)
        return queryset

    def filter_status(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        if not key or key in ("all", "all_vendors"):
            return queryset
        if key not in Vendor.Status.values:
            return queryset.none()
        return queryset.filter(status=key)
