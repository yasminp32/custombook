import django_filters

from apps.audit_logs.models import AuditLog


class AuditLogFilter(django_filters.FilterSet):
    audit_log_id = django_filters.NumberFilter(field_name="id")
    id = django_filters.NumberFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    user_id = django_filters.UUIDFilter(field_name="user_id")
    entity_type = django_filters.CharFilter(lookup_expr="iexact")
    entity_id = django_filters.UUIDFilter(field_name="entity_id")
    action = django_filters.CharFilter(lookup_expr="iexact")
    occurred_at = django_filters.DateTimeFilter()
    occurred_at_from = django_filters.DateTimeFilter(field_name="occurred_at", lookup_expr="gte")
    occurred_at_to = django_filters.DateTimeFilter(field_name="occurred_at", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = (
            "audit_log_id",
            "id",
            "organization_id",
            "user_id",
            "entity_type",
            "entity_id",
            "action",
            "occurred_at",
        )
