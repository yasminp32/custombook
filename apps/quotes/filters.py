from django.db.models import Q
import django_filters

from apps.quotes.models import Quote

QUOTE_TAB_FILTERS = (
    ("all", "All"),
    ("draft", "Draft"),
    ("sent", "Sent"),
)

QUOTE_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("draft", "Draft"),
    ("sent", "Sent"),
    ("accepted", "Accepted"),
    ("declined", "Declined"),
    ("expired", "Expired"),
    ("converted", "Converted"),
)


class QuoteFilter(django_filters.FilterSet):
    quote_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    quote_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=QUOTE_STATUS_FILTERS, method="filter_status")
    quote_date = django_filters.DateFilter()
    quote_date_from = django_filters.DateFilter(field_name="quote_date", lookup_expr="gte")
    quote_date_to = django_filters.DateFilter(field_name="quote_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.ChoiceFilter(choices=QUOTE_TAB_FILTERS, method="filter_tab")

    class Meta:
        model = Quote
        fields = (
            "quote_id",
            "id",
            "organization_id",
            "customer_id",
            "quote_number",
            "status",
            "quote_date",
            "quote_date_from",
            "quote_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(quote_number__icontains=value)
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
        status_value = (self.data.get("status") or "").strip().lower()
        if status_value and status_value not in ("", "all_statuses"):
            return queryset
        if value in ("draft", "sent"):
            return queryset.filter(status=value)
        return queryset

    def filter_status(self, queryset, name, value):
        if not value or value == "all_statuses":
            return queryset
        return queryset.filter(status=value)
