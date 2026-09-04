import django_filters

from apps.payment_terms.models import PaymentTerm


class PaymentTermFilter(django_filters.FilterSet):
    payment_term_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    name = django_filters.CharFilter(lookup_expr="icontains")
    due_days = django_filters.NumberFilter()
    is_default = django_filters.BooleanFilter()

    class Meta:
        model = PaymentTerm
        fields = (
            "payment_term_id",
            "id",
            "organization_id",
            "name",
            "due_days",
            "is_default",
        )
