from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.banking.constants import BANKING_CURRENCIES
from apps.banking.filters import BankAccountFilter, BankTransactionFilter
from apps.banking.models import BankAccount, BankTransaction
from apps.banking.periods import DATE_RANGE_LABELS, DATE_RANGES, get_date_range
from apps.banking.serializers import (
    BankAccountSerializer,
    BankAccountWriteSerializer,
    BankTransactionSerializer,
    BankTransactionWriteSerializer,
)
from apps.banking.services import build_overview
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def require_organization(request, organization_id=None):
    organization = resolve_organization(
        request.user,
        organization_id or request.query_params.get("organization_id"),
    )
    if not organization:
        return None, api_error(
            "Organization not found. Complete organization setup first.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return organization, None


def get_account_queryset(user):
    return BankAccount.objects.filter(organization__owner=user).select_related(
        "organization",
        "created_by",
    )


def get_transaction_queryset(user):
    return BankTransaction.objects.filter(organization__owner=user).select_related(
        "organization",
        "account",
    )


def get_account_id_param(request):
    account_id = request.query_params.get("account_id") or request.query_params.get("id")
    if not account_id or account_id == "all":
        return None, api_error(
            "account_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return account_id, None


def get_transaction_id_param(request):
    transaction_id = (
        request.query_params.get("transaction_id")
        or request.query_params.get("id")
    )
    if not transaction_id:
        return None, api_error(
            "transaction_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return transaction_id, None


class BankingOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = require_organization(request)
        if error_response:
            return error_response
        date_range = (request.query_params.get("date_range") or "last_30_days").strip().lower()
        if date_range not in DATE_RANGES:
            return api_error(
                "Invalid date_range.",
                errors={"date_range": f"Allowed values: {', '.join(DATE_RANGES)}."},
            )
        return api_success(data=build_overview(organization, request.query_params))


class BankingRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = require_organization(
            request,
            request.data.get("organization_id"),
        )
        if error_response:
            return error_response
        return api_success(
            data=build_overview(organization, request.query_params),
            message="Balances refreshed.",
        )


class BankAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account_id = request.query_params.get("account_id") or request.query_params.get("id")
        if account_id and account_id != "all":
            account = get_object_or_404(get_account_queryset(request.user), pk=account_id)
            return api_success(data=BankAccountSerializer(account).data)

        queryset = get_account_queryset(request.user)
        params = request.query_params.copy()
        if "status" not in params:
            params["status"] = BankAccount.Status.ACTIVE

        account_filter = BankAccountFilter(params, queryset=queryset)
        if not account_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=account_filter.errors)

        response = paginate_queryset(
            request,
            account_filter.qs.order_by("name"),
            serializer=BankAccountSerializer,
        )
        if response is not None:
            return response
        return api_success(data=[])

    def post(self, request):
        organization, error_response = require_organization(
            request,
            request.data.get("organization_id"),
        )
        if error_response:
            return error_response

        serializer = BankAccountWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            account = serializer.save(organization=organization, created_by=request.user)
        except IntegrityError:
            return api_error(
                "An account with this name or code already exists in the organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return api_success(
            data=BankAccountSerializer(account).data,
            message="Bank account created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        account_id, error_response = get_account_id_param(request)
        if error_response:
            return error_response
        account = get_object_or_404(get_account_queryset(request.user), pk=account_id)
        serializer = BankAccountWriteSerializer(account, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            account = serializer.save()
        except IntegrityError:
            return api_error(
                "An account with this name or code already exists in the organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return api_success(
            data=BankAccountSerializer(account).data,
            message="Bank account updated successfully.",
        )

    def patch(self, request):
        account_id, error_response = get_account_id_param(request)
        if error_response:
            return error_response
        account = get_object_or_404(get_account_queryset(request.user), pk=account_id)
        serializer = BankAccountWriteSerializer(account, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            account = serializer.save()
        except IntegrityError:
            return api_error(
                "An account with this name or code already exists in the organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return api_success(
            data=BankAccountSerializer(account).data,
            message="Bank account updated successfully.",
        )

    def delete(self, request):
        account_id, error_response = get_account_id_param(request)
        if error_response:
            return error_response
        account = get_object_or_404(get_account_queryset(request.user), pk=account_id)
        account.delete()
        return api_success(message="Bank account deleted successfully.")


class BankTransactionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transaction_id = (
            request.query_params.get("transaction_id")
            or request.query_params.get("id")
        )
        if transaction_id:
            transaction = get_object_or_404(
                get_transaction_queryset(request.user),
                pk=transaction_id,
            )
            return api_success(data=BankTransactionSerializer(transaction).data)

        organization, error_response = require_organization(request)
        if error_response:
            return error_response

        queryset = get_transaction_queryset(request.user)
        params = request.query_params.copy()
        range_key = (params.get("date_range") or "").strip().lower()
        if range_key:
            if range_key not in DATE_RANGES:
                return api_error(
                    "Invalid date_range.",
                    errors={"date_range": f"Allowed values: {', '.join(DATE_RANGES)}."},
                )
            _, _, start, end = get_date_range(range_key)
            params["date_from"] = start.isoformat()
            params["date_to"] = end.isoformat()

        txn_filter = BankTransactionFilter(params, queryset=queryset)
        if not txn_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=txn_filter.errors)

        response = paginate_queryset(
            request,
            txn_filter.qs.order_by("-transaction_date", "-created_at"),
            serializer=BankTransactionSerializer,
        )
        if response is not None:
            return response
        return api_success(data=[])

    def post(self, request):
        organization, error_response = require_organization(
            request,
            request.data.get("organization_id"),
        )
        if error_response:
            return error_response
        serializer = BankTransactionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            transaction = serializer.save(organization=organization)
        except serializers.ValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        return api_success(
            data=BankTransactionSerializer(transaction).data,
            message="Transaction created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        transaction_id, error_response = get_transaction_id_param(request)
        if error_response:
            return error_response
        transaction = get_object_or_404(
            get_transaction_queryset(request.user),
            pk=transaction_id,
        )
        account = transaction.account
        account.books_balance = (account.books_balance or 0) - transaction.signed_amount
        account.save(update_fields=["books_balance", "updated_at"])
        transaction.delete()
        return api_success(message="Transaction deleted successfully.")


class BankingStatementExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = require_organization(request)
        if error_response:
            return error_response
        date_range = (request.query_params.get("date_range") or "last_30_days").strip().lower()
        if date_range not in DATE_RANGES:
            return api_error(
                "Invalid date_range.",
                errors={"date_range": f"Allowed values: {', '.join(DATE_RANGES)}."},
            )
        range_key, range_label, start, end = get_date_range(date_range)
        queryset = get_transaction_queryset(request.user).filter(
            transaction_date__range=(start, end),
        )
        account_id = request.query_params.get("account_id")
        if account_id and account_id != "all":
            queryset = queryset.filter(account_id=account_id)

        return api_success(
            data={
                "title": "Bank Statement",
                "date_range": range_key,
                "date_range_label": range_label,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "count": queryset.count(),
                "transactions": BankTransactionSerializer(queryset, many=True).data,
            },
            message="Statement exported successfully.",
        )


class BankingOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search = (request.query_params.get("search") or "").strip().lower()
        currencies = BANKING_CURRENCIES
        if search:
            currencies = [
                option
                for option in BANKING_CURRENCIES
                if search in option["value"].lower() or search in option["label"].lower()
            ]
        return api_success(
            data={
                "account_types": [
                    {"key": key, "label": label}
                    for key, label in BankAccount.AccountType.choices
                ],
                "statuses": [
                    {"key": key, "label": label}
                    for key, label in BankAccount.Status.choices
                ],
                "date_ranges": [
                    {"key": key, "label": DATE_RANGE_LABELS[key]} for key in DATE_RANGES
                ],
                "currencies": currencies,
            }
        )
