import django_filters

from apps.vendors.models import Vendor


class VendorFilter(django_filters.FilterSet):
    vendor_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    display_name = django_filters.CharFilter(lookup_expr="icontains")
    gstin = django_filters.CharFilter(lookup_expr="icontains")
    payment_term_id = django_filters.UUIDFilter(field_name="payment_term_id")
    status = django_filters.ChoiceFilter(choices=Vendor.Status.choices)

    class Meta:
        model = Vendor
        fields = (
            "vendor_id",
            "id",
            "organization_id",
            "display_name",
            "gstin",
            "payment_term_id",
            "status",
        )
