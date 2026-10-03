from django.db import IntegrityError
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.taxes import constants
from apps.taxes.models import TaxRate
from apps.taxes.serializers import (
    TaxPreferenceSerializer,
    TaxRateSerializer,
    TaxRateWriteSerializer,
    TaxSettingsSerializer,
)
from apps.taxes.services import (
    ensure_default_taxes,
    resolve_organization,
    save_group_members,
    set_default_tax,
    sync_organization_tax,
)

NO_ORGANIZATION_MESSAGE = "Organization not found. Complete organization setup first."
DUPLICATE_NAME_MESSAGE = "A tax with this name already exists."


def organization_id_from(request):
    return request.query_params.get("organization_id") or request.data.get("organization_id")


def load_organization(request):
    organization = resolve_organization(request.user, organization_id_from(request))
    if not organization:
        return None, api_error(NO_ORGANIZATION_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)
    ensure_default_taxes(organization)
    return organization, None


def tax_queryset(user):
    return TaxRate.objects.filter(organization__owner=user).prefetch_related("members")


def get_tax_id(request):
    return request.query_params.get("tax_id") or request.query_params.get("id")


class TaxIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        sections = [
            ("rates", "Tax Rates", "/api/taxes/rates/"),
            ("settings", "Tax Settings", "/api/taxes/settings/"),
            ("preferences", "Tax Preferences", "/api/taxes/preferences/"),
        ]
        return api_success(
            data={
                "organization_id": str(organization.id),
                "organization_name": organization.name,
                "sections": [
                    {"code": code, "label": label, "url": request.build_absolute_uri(path)}
                    for code, label, path in sections
                ],
            }
        )


class TaxOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "tax_types": constants.options_payload(constants.TAX_TYPES),
                "reporting_periods": constants.options_payload(constants.REPORTING_PERIODS),
                "actions": constants.RATE_ACTIONS,
            }
        )


class TaxRateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tax_id = get_tax_id(request)
        if tax_id:
            tax = get_object_or_404(tax_queryset(request.user), pk=tax_id)
            return api_success(data=TaxRateSerializer(tax).data)

        organization, error = load_organization(request)
        if error:
            return error
        queryset = TaxRate.objects.filter(organization=organization).prefetch_related("members")
        search = (request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        tax_type = (request.query_params.get("tax_type") or "").strip()
        if tax_type:
            if tax_type not in dict(constants.TAX_TYPES):
                return api_error("Invalid tax_type. Allowed values: tax, group.")
            queryset = queryset.filter(tax_type=tax_type)
        rows = list(queryset.order_by("-is_default", "name"))
        return api_success(
            data={
                "count": len(rows),
                "actions": constants.RATE_ACTIONS,
                "results": TaxRateSerializer(rows, many=True).data,
            }
        )

    def post(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        serializer = TaxRateWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        tax_ids = serializer.validated_data.pop("tax_ids", None)
        name = serializer.validated_data["name"]
        if TaxRate.objects.filter(organization=organization, name__iexact=name).exists():
            return api_error(DUPLICATE_NAME_MESSAGE)
        members, member_error = self._members(organization, tax_ids, serializer.validated_data["tax_type"])
        if member_error:
            return member_error
        try:
            tax = serializer.save(organization=organization)
        except IntegrityError:
            return api_error(DUPLICATE_NAME_MESSAGE)
        if tax.tax_type == TaxRate.TaxType.GROUP:
            tax = save_group_members(tax, members)
        if tax.is_default:
            set_default_tax(tax)
        return api_success(
            data=TaxRateSerializer(tax).data,
            message="Tax group added." if tax.tax_type == TaxRate.TaxType.GROUP else "Tax added.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        tax_id = get_tax_id(request)
        if not tax_id:
            return api_error("tax_id query parameter is required.", status_code=status.HTTP_400_BAD_REQUEST)
        tax = get_object_or_404(tax_queryset(request.user), pk=tax_id)
        serializer = TaxRateWriteSerializer(tax, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        tax_ids = serializer.validated_data.pop("tax_ids", None)
        name = serializer.validated_data.get("name", tax.name)
        if (
            TaxRate.objects.filter(organization=tax.organization, name__iexact=name)
            .exclude(pk=tax.pk)
            .exists()
        ):
            return api_error(DUPLICATE_NAME_MESSAGE)
        tax_type = serializer.validated_data.get("tax_type", tax.tax_type)
        members, member_error = self._members(tax.organization, tax_ids, tax_type, tax)
        if member_error:
            return member_error
        try:
            tax = serializer.save()
        except IntegrityError:
            return api_error(DUPLICATE_NAME_MESSAGE)
        if tax.tax_type == TaxRate.TaxType.GROUP and members is not None:
            tax = save_group_members(tax, members)
        if tax.is_default:
            set_default_tax(tax)
        elif not TaxRate.objects.filter(organization=tax.organization, is_default=True).exists():
            replacement = (
                TaxRate.objects.filter(organization=tax.organization, tax_type=TaxRate.TaxType.TAX)
                .exclude(pk=tax.pk)
                .order_by("created_at")
                .first()
            )
            if replacement:
                set_default_tax(replacement)
            else:
                tax.is_default = True
                tax.save(update_fields=["is_default", "updated_at"])
        return api_success(data=TaxRateSerializer(tax).data, message="Tax updated.")

    def delete(self, request):
        tax_id = get_tax_id(request)
        if not tax_id:
            return api_error("tax_id query parameter is required.", status_code=status.HTTP_400_BAD_REQUEST)
        tax = get_object_or_404(tax_queryset(request.user), pk=tax_id)
        if tax.is_default:
            return api_error("The default tax cannot be deleted. Set another tax as the default first.")
        if tax.groups.exists():
            return api_error("This tax is used in a tax group and cannot be deleted.")
        try:
            tax.delete()
        except ProtectedError:
            return api_error("This tax is in use and cannot be deleted.")
        return api_success(message="Tax deleted.")

    def _members(self, organization, tax_ids, tax_type, current=None):
        if tax_type != TaxRate.TaxType.GROUP or tax_ids is None:
            return None, None
        unique_ids = []
        for tax_id in tax_ids:
            if tax_id not in unique_ids:
                unique_ids.append(tax_id)
        if len(unique_ids) < 2:
            return None, api_error(
                "Validation error",
                errors={"tax_ids": "Select at least two taxes for the group."},
            )
        members = list(
            TaxRate.objects.filter(
                organization=organization,
                pk__in=unique_ids,
                tax_type=TaxRate.TaxType.TAX,
            )
        )
        if current and current.pk in unique_ids:
            return None, api_error(
                "Validation error",
                errors={"tax_ids": "A tax group cannot include itself."},
            )
        if len(members) != len(unique_ids):
            return None, api_error(
                "Validation error",
                errors={"tax_ids": "Each selected tax must be a tax in this organization, not a group."},
            )
        by_id = {member.pk: member for member in members}
        return [by_id[tax_id] for tax_id in unique_ids], None


class TaxSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        return api_success(data=TaxSettingsSerializer(organization.tax_settings).data)

    def put(self, request):
        return self._save(request, partial=False)

    def patch(self, request):
        return self._save(request, partial=True)

    def _save(self, request, partial):
        organization, error = load_organization(request)
        if error:
            return error
        settings_row = organization.tax_settings
        serializer = TaxSettingsSerializer(settings_row, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        settings_row = serializer.save()
        sync_organization_tax(organization, settings_row)
        return api_success(
            data=TaxSettingsSerializer(settings_row).data,
            message="Tax settings saved.",
        )


class TaxPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        return api_success(data=TaxPreferenceSerializer(organization.tax_settings).data)

    def put(self, request):
        return self._save(request, partial=False)

    def patch(self, request):
        return self._save(request, partial=True)

    def _save(self, request, partial):
        organization, error = load_organization(request)
        if error:
            return error
        serializer = TaxPreferenceSerializer(
            organization.tax_settings,
            data=request.data,
            partial=partial,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        settings_row = serializer.save()
        return api_success(
            data=TaxPreferenceSerializer(settings_row).data,
            message="Tax preferences saved.",
        )
