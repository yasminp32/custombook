import django_filters

from apps.customers.models import CustomerPayment


class CustomerPaymentFilter(django_filters.FilterSet):
    customer_payment_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    payment_number = django_filters.CharFilter(lookup_expr="icontains")
    payment_mode_id = django_filters.UUIDFilter(field_name="payment_mode_id")
    bank_account_id = django_filters.UUIDFilter(field_name="bank_account_id")
    reference_number = django_filters.CharFilter(lookup_expr="icontains")
    payment_date = django_filters.DateFilter()
    payment_date_from = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    payment_date_to = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")

    class Meta:
        model = CustomerPayment
        fields = (
            "customer_payment_id",
            "id",
            "organization_id",
            "customer_id",
            "payment_number",
            "payment_mode_id",
            "bank_account_id",
            "reference_number",
            "payment_date",
        )
