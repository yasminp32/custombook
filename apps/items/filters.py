import django_filters
from django.db.models import Q

from apps.items.models import Item

ITEM_FILTERS = (
    ("all_items", "All Items"),
    ("active_items", "Active Items"),
    ("inactive_items", "Inactive Items"),
    ("sales", "Sales"),
    ("purchases", "Purchases"),
    ("services", "Services"),
    ("zoho_crm", "Zoho CRM"),
    ("inventory_items", "Inventory Items"),
    ("non_inventory_items", "Non-inventory Items"),
)


class ItemFilter(django_filters.FilterSet):
    item_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    name = django_filters.CharFilter(lookup_expr="icontains")
    sku = django_filters.CharFilter(lookup_expr="iexact")
    item_type = django_filters.ChoiceFilter(choices=Item.ItemType.choices)
    status = django_filters.ChoiceFilter(choices=Item.Status.choices)
    sales_enabled = django_filters.BooleanFilter()
    purchase_enabled = django_filters.BooleanFilter()
    track_inventory = django_filters.BooleanFilter()
    preferred_vendor_id = django_filters.UUIDFilter(field_name="preferred_vendor_id")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.ChoiceFilter(choices=ITEM_FILTERS, method="filter_preset")

    class Meta:
        model = Item
        fields = (
            "item_id",
            "id",
            "organization_id",
            "name",
            "sku",
            "item_type",
            "status",
            "sales_enabled",
            "purchase_enabled",
            "track_inventory",
            "preferred_vendor_id",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(sku__icontains=value))

    def filter_preset(self, queryset, name, value):
        presets = {
            "all_items": queryset,
            "active_items": queryset.filter(status=Item.Status.ACTIVE),
            "inactive_items": queryset.filter(status=Item.Status.INACTIVE),
            "sales": queryset.filter(sales_enabled=True),
            "purchases": queryset.filter(purchase_enabled=True),
            "services": queryset.filter(item_type=Item.ItemType.SERVICE),
            "zoho_crm": queryset.filter(synced_with_crm=True),
            "inventory_items": queryset.filter(track_inventory=True),
            "non_inventory_items": queryset.filter(track_inventory=False),
        }
        return presets.get(value, queryset)
