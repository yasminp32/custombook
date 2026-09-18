from datetime import date

from django.db.models import F, Q
import django_filters

from apps.payments_received.models import PaymentReceived

PAYMENT_TAB_FILTERS = (
    ("all", "All"),
    ("this_month", "This Month"),
    ("unapplied", "Unapplied"),
)

PAYMENT_MODE_FILTERS = (
    ("all_modes", "All Modes"),
    ("cash", "Cash"),
    ("bank_transfer", "Bank Transfer"),
    ("card", "Card"),
    ("cheque", "Cheque"),
    ("upi", "UPI"),
)

PAYMENT_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("unapplied", "Unapplied"),
    ("applied", "Applied"),
)


class PaymentReceivedFilter(django_filters.FilterSet):
    payment_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    payment_number = django_filters.CharFilter(lookup_expr="icontains")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")
    payment_mode = django_filters.CharFilter(method="filter_mode")
    mode = django_filters.CharFilter(method="filter_mode")
    status = django_filters.CharFilter(method="filter_status")
    payment_date = django_filters.DateFilter()
    payment_date_from = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    payment_date_to = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = PaymentReceived
        fields = (
            "payment_id",
            "id",
            "organization_id",
            "customer_id",
            "payment_number",
            "reference_number",
            "payment_mode",
            "mode",
            "status",
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
        if key == "this_month":
            today = date.today()
            return queryset.filter(
                payment_date__year=today.year,
                payment_date__month=today.month,
            )
        if key == "unapplied":
            return queryset.filter(amount_applied__lt=F("amount"))
        return queryset

    def filter_status(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        if not key or key in ("all", "all_statuses"):
            return queryset
        if key == "unapplied":
            return queryset.filter(amount_applied__lt=F("amount"))
        if key == "applied":
            return queryset.filter(amount_applied__gte=F("amount"))
        return queryset.none()

    def filter_mode(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
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
