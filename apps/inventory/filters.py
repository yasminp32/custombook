import django_filters
from django.db.models import Q

from apps.inventory.models import InventoryAdjustment

ADJUSTMENT_FILTERS = (
    ("all", "All"),
    ("by_quantity", "By Quantity"),
    ("by_value", "By Value"),
)


class InventoryAdjustmentFilter(django_filters.FilterSet):
    adjustment_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    reason = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=InventoryAdjustment.Status.choices)
    adjustment_type = django_filters.ChoiceFilter(
        choices=InventoryAdjustment.AdjustmentType.choices
    )
    date = django_filters.DateFilter()
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.ChoiceFilter(
        choices=ADJUSTMENT_FILTERS,
        method="filter_preset",
    )

    class Meta:
        model = InventoryAdjustment
        fields = (
            "adjustment_id",
            "id",
            "organization_id",
            "reason",
            "status",
            "adjustment_type",
            "date",
            "date_from",
            "date_to",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(reason__icontains=value)
            | Q(adjusted_by_name__icontains=value)
            | Q(reference_number__icontains=value)
        )

    def filter_preset(self, queryset, name, value):
        presets = {
            "all": queryset,
            "by_quantity": queryset.filter(
                adjustment_type=InventoryAdjustment.AdjustmentType.QUANTITY
            ),
            "by_value": queryset.filter(
                adjustment_type=InventoryAdjustment.AdjustmentType.VALUE
            ),
        }
        return presets.get(value, queryset)
