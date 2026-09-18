from django.db.models import Q
import django_filters

from apps.time_entries.models import TimeEntry

TIME_ENTRY_TAB_FILTERS = (
    ("all", "All"),
    ("billable", "Billable"),
    ("non_billable", "Non-billable"),
)

TIME_ENTRY_TYPE_FILTERS = (
    ("all_entries", "All Entries"),
    ("billable", "BILLABLE"),
    ("non_billable", "NON-BILLABLE"),
)


def normalize_key(value):
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_").rstrip(".")


class TimeEntryFilter(django_filters.FilterSet):
    time_entry_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    project_id = django_filters.UUIDFilter(field_name="project_id")
    user_id = django_filters.UUIDFilter(field_name="user_id")
    task_name = django_filters.CharFilter(lookup_expr="icontains")
    is_billable = django_filters.BooleanFilter()
    type = django_filters.CharFilter(method="filter_type")
    status = django_filters.CharFilter(method="filter_type")
    log_date = django_filters.DateFilter()
    log_date_from = django_filters.DateFilter(field_name="log_date", lookup_expr="gte")
    log_date_to = django_filters.DateFilter(field_name="log_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = TimeEntry
        fields = (
            "time_entry_id",
            "id",
            "organization_id",
            "project_id",
            "user_id",
            "task_name",
            "is_billable",
            "type",
            "status",
            "log_date",
            "log_date_from",
            "log_date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(task_name__icontains=value)
            | Q(notes__icontains=value)
            | Q(project__name__icontains=value)
            | Q(user__email__icontains=value)
            | Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        type_value = normalize_key(self.data.get("type") or self.data.get("status"))
        if type_value and type_value not in ("", "all", "all_entries"):
            return queryset
        key = normalize_key(value)
        if key == "billable":
            return queryset.filter(is_billable=True)
        if key == "non_billable":
            return queryset.filter(is_billable=False)
        return queryset

    def filter_type(self, queryset, name, value):
        key = normalize_key(value)
        if not key or key in ("all", "all_entries"):
            return queryset
        if key == "billable":
            return queryset.filter(is_billable=True)
        if key == "non_billable":
            return queryset.filter(is_billable=False)
        return queryset.none()
