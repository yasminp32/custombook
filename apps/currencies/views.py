from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.currencies import constants
from apps.currencies.models import Currency
from apps.currencies.serializers import CurrencySerializer, CurrencyWriteSerializer
from apps.currencies.services import (
    catalog_entry,
    currency_in_use,
    ensure_default_currencies,
    resolve_organization,
)

NO_ORGANIZATION_MESSAGE = "Organization not found. Complete organization setup first."
DUPLICATE_MESSAGE = "This currency has already been added to your organization."


def get_currency_queryset(user):
    return Currency.objects.filter(organization__owner=user).select_related("organization")


def get_currency_id(request):
    return request.query_params.get("currency_id") or request.query_params.get("id")


def load_organization(request):
    organization = resolve_organization(
        request.user,
        request.query_params.get("organization_id") or request.data.get("organization_id"),
    )
    if not organization:
        return None, api_error(NO_ORGANIZATION_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)
    ensure_default_currencies(organization)
    return organization, None


def sort_currencies(queryset, organization, sort_by):
    base_code = (organization.currency or "").upper()
    rows = list(queryset)
    key = (lambda row: row.name.lower()) if sort_by == "name" else (lambda row: row.code)
    rows.sort(key=key)
    rows.sort(key=lambda row: 0 if row.code == base_code else 1)
    return rows


class CurrencyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        currency_id = get_currency_id(request)
        if currency_id:
            currency = get_object_or_404(get_currency_queryset(request.user), pk=currency_id)
            return api_success(data=CurrencySerializer(currency).data)

        organization, error = load_organization(request)
        if error:
            return error

        sort_by = (request.query_params.get("sort_by") or "code").lower()
        if sort_by not in {"code", "name"}:
            return api_error(
                "Invalid sort_by. Allowed values: code, name.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        queryset = Currency.objects.filter(organization=organization)
        search = (request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(code__icontains=search) | queryset.filter(
                name__icontains=search
            )
        rows = sort_currencies(queryset, organization, sort_by)
        return api_success(
            data={
                "base_currency": (organization.currency or "").upper(),
                "sort_by": sort_by,
                "notice": constants.FTA_NOTICE if (organization.country or "").upper() == "AE" else None,
                "count": len(rows),
                "results": CurrencySerializer(rows, many=True).data,
            }
        )

    def post(self, request):
        organization, error = load_organization(request)
        if error:
            return error

        serializer = CurrencyWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        code = serializer.validated_data["code"]
        if Currency.objects.filter(organization=organization, code=code).exists():
            return api_error(DUPLICATE_MESSAGE)
        try:
            currency = serializer.save(organization=organization)
        except IntegrityError:
            return api_error(DUPLICATE_MESSAGE)
        return api_success(
            data=CurrencySerializer(currency).data,
            message="Currency added successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        currency_id = get_currency_id(request)
        if not currency_id:
            return api_error(
                "currency_id query parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        currency = get_object_or_404(get_currency_queryset(request.user), pk=currency_id)
        serializer = CurrencyWriteSerializer(currency, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        new_code = serializer.validated_data.get("code", currency.code)
        if new_code != currency.code:
            if currency.is_base:
                return api_error("The base currency code cannot be changed.")
            if Currency.objects.filter(organization=currency.organization, code=new_code).exists():
                return api_error(DUPLICATE_MESSAGE)
        try:
            currency = serializer.save()
        except IntegrityError:
            return api_error(DUPLICATE_MESSAGE)
        return api_success(
            data=CurrencySerializer(currency).data,
            message="Currency updated successfully.",
        )

    def delete(self, request):
        currency_id = get_currency_id(request)
        if not currency_id:
            return api_error(
                "currency_id query parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        currency = get_object_or_404(get_currency_queryset(request.user), pk=currency_id)
        if currency.is_base:
            return api_error("The base currency cannot be deleted.")
        if currency_in_use(currency):
            return api_error(
                "This currency is used by one or more customers and cannot be deleted."
            )
        currency.delete()
        return api_success(message="Currency deleted successfully.")


class CurrencyOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        added = set(
            Currency.objects.filter(organization=organization).values_list("code", flat=True)
        )
        codes = []
        for code in constants.CURRENCY_CODE_OPTIONS:
            entry = catalog_entry(code)
            codes.append(
                {
                    "code": code,
                    "name": entry["name"],
                    "symbol": entry["symbol"],
                    "decimal_places": entry["decimal_places"],
                    "already_added": code in added,
                }
            )
        return api_success(
            data={
                "currency_codes": codes,
                "available_currency_codes": [row for row in codes if not row["already_added"]],
                "decimal_places": list(constants.DECIMAL_PLACES_OPTIONS),
                "formats": [
                    {"value": value, "label": label} for value, label in constants.FORMAT_OPTIONS
                ],
                "sort_options": [
                    {
                        "value": "code",
                        "label": "Sort by Currency Code",
                        "description": "Arrange currencies alphabetically by code",
                    },
                    {
                        "value": "name",
                        "label": "Sort by Currency Name",
                        "description": "Arrange currencies alphabetically by name",
                    },
                ],
            }
        )
