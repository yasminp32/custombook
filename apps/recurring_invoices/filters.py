from datetime import date

from django.db.models import Q
import django_filters

from apps.recurring_invoices.models import RecurringInvoice

PROFILE_TAB_FILTERS = (
    ("all", "All"),
    ("active", "Active"),
    ("stopped", "Stopped"),
)

PROFILE_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("active", "ACTIVE"),
    ("stopped", "STOPPED"),
    ("expired", "EXPIRED"),
    ("draft", "DRAFT"),
)


def expired_q():
    return Q(status=RecurringInvoice.Status.EXPIRED) | Q(
        status=RecurringInvoice.Status.ACTIVE,
        end_date__lt=date.today(),
    )


class RecurringInvoiceFilter(django_filters.FilterSet):
    recurring_invoice_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    profile_name = django_filters.CharFilter(lookup_expr="icontains")
    frequency = django_filters.CharFilter(method="filter_frequency")
    status = django_filters.CharFilter(method="filter_status")
    start_date = django_filters.DateFilter()
    start_date_from = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_to = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = RecurringInvoice
        fields = (
            "recurring_invoice_id",
            "id",
            "organization_id",
            "customer_id",
            "profile_name",
            "frequency",
            "status",
            "start_date",
            "start_date_from",
            "start_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(profile_name__icontains=value)
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
        if key == "active":
            return queryset.filter(status=RecurringInvoice.Status.ACTIVE).exclude(expired_q())
        if key == "stopped":
            return queryset.filter(status=RecurringInvoice.Status.STOPPED)
        return queryset

    def filter_status(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        if not key or key in ("all", "all_statuses"):
            return queryset
        if key == "expired":
            return queryset.filter(expired_q())
        if key == "active":
            return queryset.filter(status=RecurringInvoice.Status.ACTIVE).exclude(expired_q())
        allowed = {choice[0] for choice in PROFILE_STATUS_FILTERS}
        if key not in allowed:
            return queryset.none()
        return queryset.filter(status=key)

    def filter_frequency(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        aliases = {
            "weekly": "weekly",
            "week": "weekly",
            "monthly": "monthly",
            "month": "monthly",
            "quarterly": "quarterly",
            "quarter": "quarterly",
            "yearly": "yearly",
            "year": "yearly",
            "annually": "yearly",
            "annual": "yearly",
        }
        mapped = aliases.get(key)
        if not mapped:
            return queryset.none()
        return queryset.filter(frequency=mapped)
