from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.inventory.filters import ADJUSTMENT_FILTERS, InventoryAdjustmentFilter
from apps.inventory.models import InventoryAdjustment
from apps.inventory.serializers import (
    InventoryAdjustmentSerializer,
    InventoryAdjustmentWriteSerializer,
)
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset

SORT_FIELDS = {
    "date": "date",
    "reason": "reason",
    "created_time": "created_at",
    "created_at": "created_at",
    "last_modified_time": "updated_at",
    "updated_at": "updated_at",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_adjustment_queryset(user):
    return InventoryAdjustment.objects.filter(organization__owner=user).select_related(
        "organization",
        "created_by",
    ).prefetch_related("lines__item")


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_adjustment_id_param(request):
    adjustment_id = (
        request.query_params.get("adjustment_id")
        or request.query_params.get("id")
    )
    if not adjustment_id:
        return None, api_error(
            "adjustment_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return adjustment_id, None


def apply_sorting(queryset, query_params):
    sort_by = (query_params.get("sort_by") or "created_time").strip().lower()
    sort_order = (query_params.get("sort_order") or "desc").strip().lower()
    field = SORT_FIELDS.get(sort_by)
    if not field:
        return None, api_error(
            "Invalid sort_by.",
            errors={"sort_by": f"Allowed values: {', '.join(SORT_FIELDS.keys())}."},
        )
    if sort_order not in ("asc", "desc"):
        return None, api_error(
            "Invalid sort_order.",
            errors={"sort_order": "Allowed values: asc, desc."},
        )
    prefix = "-" if sort_order == "desc" else ""
    return queryset.order_by(f"{prefix}{field}", "-created_at"), None


class InventoryAdjustmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        adjustment_id = (
            request.query_params.get("adjustment_id")
            or request.query_params.get("id")
        )
        if adjustment_id:
            adjustment = get_object_or_404(
                get_adjustment_queryset(request.user),
                pk=adjustment_id,
            )
            return api_success(data=InventoryAdjustmentSerializer(adjustment).data)

        queryset = get_adjustment_queryset(request.user)
        params = request.query_params.copy()
        if "filter" not in params:
            params["filter"] = "all"

        adjustment_filter = InventoryAdjustmentFilter(params, queryset=queryset)
        if not adjustment_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=adjustment_filter.errors)

        queryset, error_response = apply_sorting(
            adjustment_filter.qs,
            request.query_params,
        )
        if error_response:
            return error_response

        response = paginate_queryset(
            request,
            queryset,
            serializer=InventoryAdjustmentSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        organization = resolve_organization(
            request.user,
            request.data.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup before creating adjustments.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InventoryAdjustmentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            adjustment = serializer.save(
                organization=organization,
                created_by=request.user,
            )
        except serializers.ValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        return api_success(
            data=InventoryAdjustmentSerializer(adjustment).data,
            message="Inventory adjustment created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        adjustment_id, error_response = get_adjustment_id_param(request)
        if error_response:
            return error_response

        adjustment = get_object_or_404(
            get_adjustment_queryset(request.user),
            pk=adjustment_id,
        )
        serializer = InventoryAdjustmentWriteSerializer(adjustment, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            adjustment = serializer.save()
        except serializers.ValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        return api_success(
            data=InventoryAdjustmentSerializer(adjustment).data,
            message="Inventory adjustment updated successfully.",
        )

    def patch(self, request):
        adjustment_id, error_response = get_adjustment_id_param(request)
        if error_response:
            return error_response

        adjustment = get_object_or_404(
            get_adjustment_queryset(request.user),
            pk=adjustment_id,
        )
        serializer = InventoryAdjustmentWriteSerializer(
            adjustment,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            adjustment = serializer.save()
        except serializers.ValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        return api_success(
            data=InventoryAdjustmentSerializer(adjustment).data,
            message="Inventory adjustment updated successfully.",
        )

    def delete(self, request):
        adjustment_id, error_response = get_adjustment_id_param(request)
        if error_response:
            return error_response

        adjustment = get_object_or_404(
            get_adjustment_queryset(request.user),
            pk=adjustment_id,
        )
        if adjustment.status == InventoryAdjustment.Status.COMPLETED:
            return api_error(
                "Completed adjustments cannot be deleted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        adjustment.delete()
        return api_success(message="Inventory adjustment deleted successfully.")


class InventoryAdjustmentOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "adjustment_types": [
                    {"key": key, "label": label}
                    for key, label in InventoryAdjustment.AdjustmentType.choices
                ],
                "statuses": [
                    {"key": key, "label": label}
                    for key, label in InventoryAdjustment.Status.choices
                ],
                "filters": [
                    {"key": key, "label": label} for key, label in ADJUSTMENT_FILTERS
                ],
                "sort_fields": [
                    {"key": "date", "label": "Date"},
                    {"key": "reason", "label": "Reason"},
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "last_modified_time", "label": "Last Modified Time"},
                ],
                "reasons": [
                    "Damaged goods",
                    "Stock count correction",
                    "Warehouse transfer shortfall",
                    "Stolen goods",
                    "Write off",
                    "Other",
                ],
                "accounts": ["Inventory Asset"],
            }
        )
