import django_filters

from apps.customers.models import CustomerAddress


class CustomerAddressFilter(django_filters.FilterSet):
    customer_address_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    address_id = django_filters.UUIDFilter(field_name="address_id")
    address_type = django_filters.ChoiceFilter(choices=CustomerAddress.AddressType.choices)

    class Meta:
        model = CustomerAddress
        fields = (
            "customer_address_id",
            "id",
            "customer_id",
            "address_id",
            "address_type",
        )
