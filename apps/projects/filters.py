from django.db.models import Q
import django_filters

from apps.projects.models import Project

PROJECT_TAB_FILTERS = (
    ("all", "All"),
    ("active", "Active"),
    ("completed", "Completed"),
)

PROJECT_STATUS_FILTERS = (
    ("all_statuses", "All Statuses"),
    ("active", "ACTIVE"),
    ("on_hold", "ON HOLD"),
    ("completed", "COMPLETED"),
    ("cancelled", "CANCELLED"),
)


def normalize_key(value):
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_").rstrip(".")


class ProjectFilter(django_filters.FilterSet):
    project_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    name = django_filters.CharFilter(lookup_expr="icontains")
    billing_method = django_filters.CharFilter(method="filter_billing_method")
    status = django_filters.CharFilter(method="filter_status")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_tab")

    class Meta:
        model = Project
        fields = (
            "project_id",
            "id",
            "organization_id",
            "customer_id",
            "name",
            "billing_method",
            "status",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(customer__display_name__icontains=value)
            | Q(customer__company_name__icontains=value)
            | Q(customer__first_name__icontains=value)
            | Q(customer__last_name__icontains=value)
        )

    def filter_tab(self, queryset, name, value):
        status_value = normalize_key(self.data.get("status"))
        if status_value and status_value not in ("", "all", "all_statuses"):
            return queryset
        key = normalize_key(value)
        if key in ("active", "completed"):
            return queryset.filter(status=key)
        return queryset

    def filter_status(self, queryset, name, value):
        key = normalize_key(value)
        if not key or key in ("all", "all_statuses"):
            return queryset
        allowed = {choice[0] for choice in PROJECT_STATUS_FILTERS}
        if key not in allowed:
            return queryset.none()
        return queryset.filter(status=key)

    def filter_billing_method(self, queryset, name, value):
        key = normalize_key(value)
        aliases = {
            "fixed_cost": "fixed_cost",
            "fixed_cost_for_project": "fixed_cost",
            "project_hours": "project_hours",
            "based_on_project_hours": "project_hours",
            "staff_hours": "staff_hours",
            "based_on_staff_hours": "staff_hours",
            "task_hours": "task_hours",
            "based_on_task_hours": "task_hours",
        }
        mapped = aliases.get(key, key)
        allowed = {choice[0] for choice in Project.BillingMethod.choices}
        if mapped not in allowed:
            return queryset.none()
        return queryset.filter(billing_method=mapped)
