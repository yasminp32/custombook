import django_filters
from django.db.models import Q

from apps.banking.models import BankAccount, BankTransaction


class BankAccountFilter(django_filters.FilterSet):
    account_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    name = django_filters.CharFilter(lookup_expr="icontains")
    account_type = django_filters.ChoiceFilter(choices=BankAccount.AccountType.choices)
    status = django_filters.ChoiceFilter(choices=BankAccount.Status.choices)
    currency = django_filters.CharFilter(lookup_expr="iexact")
    is_primary = django_filters.BooleanFilter()
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = BankAccount
        fields = (
            "account_id",
            "id",
            "organization_id",
            "name",
            "account_type",
            "status",
            "currency",
            "is_primary",
            "search",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(account_code__icontains=value)
            | Q(bank_name__icontains=value)
            | Q(account_number__icontains=value)
        )


class BankTransactionFilter(django_filters.FilterSet):
    transaction_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    account_id = django_filters.UUIDFilter(field_name="account_id")
    transaction_type = django_filters.ChoiceFilter(
        choices=BankTransaction.TransactionType.choices
    )
    date_from = django_filters.DateFilter(field_name="transaction_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="transaction_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = BankTransaction
        fields = (
            "transaction_id",
            "id",
            "organization_id",
            "account_id",
            "transaction_type",
            "date_from",
            "date_to",
            "search",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(description__icontains=value)
            | Q(reference_number__icontains=value)
            | Q(account__name__icontains=value)
        )
