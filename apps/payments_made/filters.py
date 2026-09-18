from datetime import date

from django.db.models import Q
import django_filters

from apps.payments_made.models import PaymentMade

PAYMENT_TAB_FILTERS = (
    ("all", "All"),
    ("this_month", "This Month"),
)

PAYMENT_MODE_FILTERS = (
    ("all_modes", "All Modes"),
    ("cash", "Cash"),
    ("bank_transfer", "Bank Transfer"),
    ("card", "Card"),
    ("cheque", "Cheque"),
    ("upi", "UPI"),
)


def normalize_key(value):
    return (value or "").strip().lower().replace(" ", "_").rstrip(".")


class PaymentMadeFilter(django_filters.FilterSet):
    payment_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    vendor_id = django_filters.UUIDFilter(field_name="vendor_id")
    payment_number = django_filters.CharFilter(lookup_expr="icontains")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")
    payment_mode = django_filters.CharFilter(method="filter_mode")
    mode = django_filters.CharFilter(method="filter_mode")
    payment_date = django_filters.DateFilter()
    payment_date_from = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    payment_date_to = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = PaymentMade
        fields = (
            "payment_id",
            "id",
            "organization_id",
            "vendor_id",
            "payment_number",
            "reference_number",
            "payment_mode",
            "mode",
            "payment_date",
            "payment_date_from",
            "payment_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(payment_number__icontains=value)
            | Q(reference_number__icontains=value)
            | Q(vendor__display_name__icontains=value)
            | Q(vendor__company_name__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        key = normalize_key(value)
        if key == "this_month":
            today = date.today()
            return queryset.filter(
                payment_date__year=today.year,
                payment_date__month=today.month,
            )
        return queryset

    def filter_mode(self, queryset, name, value):
        key = normalize_key(value)
        aliases = {
            "all_modes": "",
            "all": "",
            "cash": "cash",
            "bank_transfer": "bank_transfer",
            "banktransfer": "bank_transfer",
            "card": "card",
            "cheque": "cheque",
            "check": "cheque",
            "upi": "upi",
        }
        mapped = aliases.get(key, key)
        if not mapped:
            return queryset
        allowed = {choice[0] for choice in PAYMENT_MODE_FILTERS if choice[0] != "all_modes"}
        if mapped not in allowed:
            return queryset.none()
        return queryset.filter(payment_mode=mapped)
