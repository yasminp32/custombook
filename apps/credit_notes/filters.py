from django.db.models import Q
import django_filters

from apps.credit_notes.models import CreditNote

CREDIT_NOTE_TAB_FILTERS = (
    ("all", "All"),
    ("open", "Open"),
    ("closed", "Closed"),
)

CREDIT_NOTE_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("draft", "DRAFT"),
    ("open", "OPEN"),
    ("closed", "CLOSED"),
    ("void", "VOID"),
)


class CreditNoteFilter(django_filters.FilterSet):
    credit_note_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    invoice_id = django_filters.UUIDFilter(field_name="invoice_id")
    credit_note_number = django_filters.CharFilter(lookup_expr="icontains")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(method="filter_status")
    credit_note_date = django_filters.DateFilter()
    credit_note_date_from = django_filters.DateFilter(
        field_name="credit_note_date",
        lookup_expr="gte",
    )
    credit_note_date_to = django_filters.DateFilter(
        field_name="credit_note_date",
        lookup_expr="lte",
    )
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = CreditNote
        fields = (
            "credit_note_id",
            "id",
            "organization_id",
            "customer_id",
            "invoice_id",
            "credit_note_number",
            "reference_number",
            "status",
            "credit_note_date",
            "credit_note_date_from",
            "credit_note_date_to",
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
        if key in ("open", "closed"):
            return queryset.filter(status=key)
        return queryset

    def filter_status(self, queryset, name, value):
        key = (value or "").strip().lower().replace(" ", "_")
        if not key or key in ("all", "all_statuses"):
            return queryset
        allowed = {choice[0] for choice in CREDIT_NOTE_STATUS_FILTERS}
        if key not in allowed:
            return queryset.none()
        return queryset.filter(status=key)
