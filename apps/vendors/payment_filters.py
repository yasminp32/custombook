import django_filters

from apps.vendors.models import VendorPayment


class VendorPaymentFilter(django_filters.FilterSet):
    vendor_payment_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    vendor_id = django_filters.UUIDFilter(field_name="vendor_id")
    payment_mode_id = django_filters.UUIDFilter(field_name="payment_mode_id")
    payment_date = django_filters.DateFilter()
    payment_date_from = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    payment_date_to = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")

    class Meta:
        model = VendorPayment
        fields = (
            "vendor_payment_id",
            "id",
            "organization_id",
            "vendor_id",
            "payment_mode_id",
            "payment_date",
        )
