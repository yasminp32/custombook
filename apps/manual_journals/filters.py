from django.db.models import Q
import django_filters

from apps.manual_journals.models import ManualJournal

MANUAL_JOURNAL_TAB_FILTERS = (
    ("all", "All"),
    ("draft", "Draft"),
    ("published", "Published"),
)

MANUAL_JOURNAL_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("draft", "DRAFT"),
    ("published", "PUBLISHED"),
)


def normalize_key(value):
    return (value or "").strip().lower().replace(" ", "_").rstrip(".")


class ManualJournalFilter(django_filters.FilterSet):
    journal_id = django_filters.UUIDFilter(field_name="id")
    manual_journal_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    journal_number = django_filters.CharFilter(lookup_expr="icontains")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(method="filter_status")
    journal_date = django_filters.DateFilter()
    journal_date_from = django_filters.DateFilter(field_name="journal_date", lookup_expr="gte")
    journal_date_to = django_filters.DateFilter(field_name="journal_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = ManualJournal
        fields = (
            "journal_id",
            "manual_journal_id",
            "id",
            "organization_id",
            "journal_number",
            "reference_number",
            "status",
            "journal_date",
            "journal_date_from",
            "journal_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(journal_number__icontains=value)
            | Q(reference_number__icontains=value)
            | Q(notes__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        status_value = normalize_key(self.data.get("status"))
        if status_value and status_value not in ("", "all", "all_statuses"):
            return queryset
        key = normalize_key(value)
        if key in ("draft", "published"):
            return queryset.filter(status=key)
        return queryset

    def filter_status(self, queryset, name, value):
        key = normalize_key(value)
        if not key or key in ("all", "all_statuses"):
            return queryset
        allowed = {choice[0] for choice in MANUAL_JOURNAL_STATUS_FILTERS}
        if key not in allowed:
            return queryset.none()
        return queryset.filter(status=key)
