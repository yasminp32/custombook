from django.db.models import Count, Q
from django.db.models.functions import Lower
import django_filters

from apps.customers.models import Customer

CUSTOMER_FILTERS = (
    ("all_customers", "All Customers"),
    ("active_customers", "Active Customers"),
    ("crm_customers", "CRM Customers"),
    ("duplicate_customers", "Duplicate Customers"),
    ("inactive_customers", "Inactive Customers"),
    ("customer_portal_enabled", "Customer Portal Enabled"),
    ("customer_portal_disabled", "Customer Portal Disabled"),
    ("overdue_customers", "Overdue Customers"),
    ("unpaid_customers", "Unpaid Customers"),
    ("associated_with_payment_options", "Associated with Payment Options"),
)


class CustomerFilter(django_filters.FilterSet):
    customer_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    display_name = django_filters.CharFilter(lookup_expr="icontains")
    company_name = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="icontains")
    phone = django_filters.CharFilter(lookup_expr="icontains")
    gstin = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=Customer.Status.choices)
    payment_term_id = django_filters.UUIDFilter(field_name="payment_term_id")
    currency_id = django_filters.UUIDFilter(field_name="currency_id")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.ChoiceFilter(choices=CUSTOMER_FILTERS, method="filter_preset")

    class Meta:
        model = Customer
        fields = (
            "customer_id",
            "id",
            "organization_id",
            "display_name",
            "company_name",
            "email",
            "phone",
            "gstin",
            "status",
            "payment_term_id",
            "currency_id",
            "search",
            "filter",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(display_name__icontains=value)
            | Q(company_name__icontains=value)
            | Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
            | Q(email__icontains=value)
            | Q(phone__icontains=value)
            | Q(mobile__icontains=value)
        )

    def filter_preset(self, queryset, name, value):
        if value == "all_customers":
            return queryset
        if value == "active_customers":
            return queryset.filter(status=Customer.Status.ACTIVE)
        if value == "inactive_customers":
            return queryset.filter(status=Customer.Status.INACTIVE)
        if value == "crm_customers":
            return queryset.filter(synced_with_crm=True)
        if value == "customer_portal_enabled":
            return queryset.filter(portal_enabled=True)
        if value == "customer_portal_disabled":
            return queryset.filter(portal_enabled=False)
        if value == "overdue_customers":
            return queryset.filter(is_overdue=True)
        if value == "unpaid_customers":
            return queryset.filter(receivables__gt=0)
        if value == "associated_with_payment_options":
            return queryset.exclude(payment_term_id=None)
        if value == "duplicate_customers":
            duplicate_names = (
                queryset.exclude(display_name="")
                .annotate(name_key=Lower("display_name"))
                .values("organization_id", "name_key")
                .annotate(total=Count("id"))
                .filter(total__gt=1)
                .values("organization_id", "name_key")
            )
            duplicate_emails = (
                queryset.exclude(email="")
                .annotate(email_key=Lower("email"))
                .values("organization_id", "email_key")
                .annotate(total=Count("id"))
                .filter(total__gt=1)
                .values("organization_id", "email_key")
            )
            name_q = Q()
            for row in duplicate_names:
                name_q |= Q(
                    organization_id=row["organization_id"],
                    display_name__iexact=row["name_key"],
                )
            email_q = Q()
            for row in duplicate_emails:
                email_q |= Q(
                    organization_id=row["organization_id"],
                    email__iexact=row["email_key"],
                )
            if not name_q and not email_q:
                return queryset.none()
            combined = name_q
            if email_q:
                combined = name_q | email_q if name_q else email_q
            return queryset.filter(combined)
        return queryset
