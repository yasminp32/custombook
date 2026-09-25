from uuid import UUID

from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.attachments.models import Attachment
from apps.inventory.filters import ADJUSTMENT_FILTERS, InventoryAdjustmentFilter
from apps.inventory.models import InventoryAdjustment, InventoryAdjustmentActivity
from apps.inventory.pdf import build_adjustment_pdf
from apps.inventory.serializers import (
    InventoryAdjustmentActivitySerializer,
    InventoryAdjustmentSerializer,
    InventoryAdjustmentWriteSerializer,
)
from apps.inventory.services import ATTACHABLE_TYPE, log_activity
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset

ACTIVITY_TYPE_FILTERS = ("all", "comment", "history")

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
    attachments_total = (
        Attachment.objects.filter(
            organization_id=OuterRef("organization_id"),
            attachable_type=ATTACHABLE_TYPE,
            attachable_id=OuterRef("pk"),
        )
        .order_by()
        .values("attachable_id")
        .annotate(total=Count("id"))
        .values("total")
    )
    return (
        InventoryAdjustment.objects.filter(organization__owner=user)
        .select_related("organization", "created_by")
        .prefetch_related("lines__item")
        .annotate(
            attachments_total=Coalesce(
                Subquery(attachments_total, output_field=IntegerField()),
                0,
            ),
            comments_total=Count(
                "activities",
                filter=Q(activities__activity_type=InventoryAdjustmentActivity.ActivityType.COMMENT),
                distinct=True,
            ),
        )
    )


def parse_uuid(value, field_name):
    raw = str(value or "").strip()
    if not raw:
        return None, api_error(
            f"{field_name} query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        return UUID(raw), None
    except (ValueError, AttributeError, TypeError):
        return None, api_error(
            f"{field_name} must be a valid UUID.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def get_adjustment_from_request(request):
    raw = request.query_params.get("adjustment_id") or request.query_params.get("id")
    adjustment_id, error_response = parse_uuid(raw, "adjustment_id")
    if error_response:
        return None, error_response
    adjustment = get_adjustment_queryset(request.user).filter(pk=adjustment_id).first()
    if not adjustment:
        return None, api_error(
            "Inventory adjustment not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return adjustment, None


def refetch(user, adjustment):
    return get_adjustment_queryset(user).get(pk=adjustment.pk)


def log_update(adjustment, previous_status, user):
    if (
        previous_status != InventoryAdjustment.Status.COMPLETED
        and adjustment.status == InventoryAdjustment.Status.COMPLETED
    ):
        log_activity(adjustment, "Inventory adjustment marked as COMPLETED.", user=user)
        log_activity(adjustment, "Stock updated for adjusted items.", user=user)
        return
    log_activity(adjustment, "Inventory adjustment updated.", user=user)


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
        log_activity(
            adjustment,
            f"Inventory adjustment created as {adjustment.get_status_display()}.",
            user=request.user,
        )
        if adjustment.status == InventoryAdjustment.Status.COMPLETED:
            log_activity(adjustment, "Stock updated for adjusted items.", user=request.user)
        return api_success(
            data=InventoryAdjustmentSerializer(refetch(request.user, adjustment)).data,
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
        previous_status = adjustment.status
        serializer = InventoryAdjustmentWriteSerializer(adjustment, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            adjustment = serializer.save()
        except serializers.ValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        log_update(adjustment, previous_status, request.user)
        return api_success(
            data=InventoryAdjustmentSerializer(refetch(request.user, adjustment)).data,
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
        previous_status = adjustment.status
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
        log_update(adjustment, previous_status, request.user)
        return api_success(
            data=InventoryAdjustmentSerializer(refetch(request.user, adjustment)).data,
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
                "attachable_type": ATTACHABLE_TYPE,
                "activity_types": [
                    {"key": key, "label": label}
                    for key, label in InventoryAdjustmentActivity.ActivityType.choices
                ],
            }
        )


class InventoryAdjustmentCommentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        adjustment, error_response = get_adjustment_from_request(request)
        if error_response:
            return error_response

        activity_type = "all"
        if "type" in request.query_params:
            activity_type = request.query_params.get("type", "").strip().lower()
            if activity_type not in ACTIVITY_TYPE_FILTERS:
                return api_error(
                    "Invalid type.",
                    errors={"type": f"Allowed values: {', '.join(ACTIVITY_TYPE_FILTERS)}."},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        queryset = adjustment.activities.select_related("created_by").order_by("created_at")
        if activity_type != "all":
            queryset = queryset.filter(activity_type=activity_type)

        response = paginate_queryset(
            request,
            queryset,
            serializer=InventoryAdjustmentActivitySerializer,
        )
        if response is not None:
            return response
        return api_success(data=[])

    def post(self, request):
        adjustment, error_response = get_adjustment_from_request(request)
        if error_response:
            return error_response

        message = str(request.data.get("message") or request.data.get("comment") or "").strip()
        if not message:
            return api_error(
                "Validation error",
                errors={"message": "Comment message is required."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        activity = log_activity(
            adjustment,
            message,
            user=request.user,
            activity_type=InventoryAdjustmentActivity.ActivityType.COMMENT,
        )
        return api_success(
            data=InventoryAdjustmentActivitySerializer(activity).data,
            message="Comment added successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class InventoryAdjustmentPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        adjustment, error_response = get_adjustment_from_request(request)
        if error_response:
            return error_response

        content = build_adjustment_pdf(adjustment)
        reference = adjustment.reference_number or str(adjustment.id)[:8]
        safe_reference = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in reference
        )
        response = HttpResponse(content, content_type="application/pdf")
        disposition = "inline" if request.query_params.get("inline") == "true" else "attachment"
        response["Content-Disposition"] = (
            f'{disposition}; filename="inventory_adjustment_{safe_reference}.pdf"'
        )
        return response
