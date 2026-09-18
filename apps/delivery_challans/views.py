from datetime import date
from uuid import UUID

from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as SerializerValidationError
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.customers.models import Customer
from apps.delivery_challans.filters import (
    CHALLAN_STATUS_FILTERS,
    CHALLAN_TAB_FILTERS,
    DeliveryChallanFilter,
)
from apps.delivery_challans.models import DeliveryChallan
from apps.delivery_challans.serializers import (
    DeliveryChallanSerializer,
    DeliveryChallanWriteSerializer,
    next_challan_number,
)
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "challan_date",
    "challan_date": "challan_date",
    "challan_number": "challan_number",
    "challan#": "challan_number",
    "customer_name": "customer__display_name",
    "amount": "total_amount",
    "total_amount": "total_amount",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_challan_queryset(user):
    return DeliveryChallan.objects.filter(organization__owner=user).select_related(
        "organization",
        "customer",
        "sales_order",
        "created_by",
    ).prefetch_related("lines__item")


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def parse_uuid(value, field_name="id"):
    if value is None or str(value).strip() == "":
        return None, api_error(
            f"{field_name} is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    raw = str(value).strip()
    if "{{" in raw or "}}" in raw:
        return None, api_error(
            f"{field_name} is still a Postman placeholder. Use the real UUID.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        return UUID(raw), None
    except (ValueError, AttributeError, TypeError):
        return None, api_error(
            f"{field_name} must be a valid UUID.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def get_challan_id_param(request):
    challan_id = (
        request.query_params.get("delivery_challan_id")
        or request.query_params.get("challan_id")
        or request.query_params.get("id")
        or request.data.get("delivery_challan_id")
        or request.data.get("challan_id")
        or request.data.get("id")
    )
    if not challan_id:
        return None, api_error(
            "delivery_challan_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(challan_id, "delivery_challan_id")


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


def filtered_challan_queryset(request):
    queryset = get_challan_queryset(request.user)
    challan_filter = DeliveryChallanFilter(request.query_params, queryset=queryset)
    if not challan_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=challan_filter.errors)
    queryset, error_response = apply_sorting(challan_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def build_challan_form(user, organization):
    queryset = get_challan_queryset(user)
    customers = Customer.objects.filter(
        organization=organization,
        status=Customer.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    items = Item.objects.filter(
        organization=organization,
        sales_enabled=True,
        status=Item.Status.ACTIVE,
    ).order_by("name")[:100]
    today = date.today()
    next_number = next_challan_number(organization)
    return {
        "title": "New Delivery Challan",
        "next_challan_number": next_number,
        "defaults": {
            "challan_number": next_number,
            "challan_date": today.isoformat(),
            "challan_date_label": today.strftime("%d %b %Y"),
            "challan_type": DeliveryChallan.ChallanType.JOB_WORK,
            "tax_type": DeliveryChallan.TaxType.EXCLUSIVE,
            "total_amount": "0.00",
            "action": "save_as_draft",
        },
        "customers": [
            {
                "customer_id": row.id,
                "display_name": row.display_name or row.company_name or row.name,
                "company_name": row.company_name or "",
                "currency": row.currency or "INR",
            }
            for row in customers
        ],
        "items": [
            {
                "item_id": row.id,
                "name": row.name,
                "sku": row.sku or "",
                "selling_price": (
                    f"{row.selling_price:.2f}" if row.selling_price is not None else "0.00"
                ),
                "tax": row.tax or "",
            }
            for row in items
        ],
        "challan_types": [
            {"key": key, "label": label} for key, label in DeliveryChallan.ChallanType.choices
        ],
        "tax_types": [
            {"key": key, "label": label} for key, label in DeliveryChallan.TaxType.choices
        ],
        "counts": {
            "all": queryset.count(),
            "draft": queryset.filter(status=DeliveryChallan.Status.DRAFT).count(),
            "delivered": queryset.filter(status=DeliveryChallan.Status.DELIVERED).count(),
        },
        "actions": [
            {
                "key": "save_as_draft",
                "label": "Save as Draft",
                "path": "/api/delivery-challans/",
            },
            {
                "key": "save_as_delivered",
                "label": "Save as Delivered",
                "path": "/api/delivery-challans/",
            },
        ],
        "create_path": "/api/delivery-challans/",
        "attachments_path": "/api/attachments/",
    }


class DeliveryChallanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        challan_id = (
            request.query_params.get("delivery_challan_id")
            or request.query_params.get("challan_id")
            or request.query_params.get("id")
        )
        if challan_id:
            parsed_id, error_response = parse_uuid(challan_id, "delivery_challan_id")
            if error_response:
                return error_response
            challan = get_challan_queryset(request.user).filter(pk=parsed_id).first()
            if not challan:
                return api_error(
                    "Delivery challan not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return api_success(data=DeliveryChallanSerializer(challan).data)

        queryset, error_response = filtered_challan_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=DeliveryChallanSerializer)
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
                "Organization not found. Complete organization setup before creating delivery challans.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = DeliveryChallanWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            challan = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Challan number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        challan = get_challan_queryset(request.user).get(pk=challan.pk)
        message = (
            "Delivery challan marked as delivered."
            if challan.status == DeliveryChallan.Status.DELIVERED
            else "Delivery challan saved as draft."
        )
        return api_success(
            data=DeliveryChallanSerializer(challan).data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        challan_id, error_response = get_challan_id_param(request)
        if error_response:
            return error_response
        challan = get_challan_queryset(request.user).filter(pk=challan_id).first()
        if not challan:
            return api_error("Delivery challan not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = DeliveryChallanWriteSerializer(challan, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            challan = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Challan number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        challan = get_challan_queryset(request.user).get(pk=challan.pk)
        return api_success(
            data=DeliveryChallanSerializer(challan).data,
            message="Delivery challan updated successfully.",
        )

    def delete(self, request):
        challan_id, error_response = get_challan_id_param(request)
        if error_response:
            return error_response
        challan = get_challan_queryset(request.user).filter(pk=challan_id).first()
        if not challan:
            return api_error("Delivery challan not found.", status_code=status.HTTP_404_NOT_FOUND)
        if challan.status == DeliveryChallan.Status.DELIVERED:
            return api_error(
                "Delivered challans cannot be deleted. Cancel or return them instead.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        challan.delete()
        return api_success(message="Delivery challan deleted successfully.")


class DeliveryChallanOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_challan_queryset(request.user)
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in CHALLAN_TAB_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in CHALLAN_STATUS_FILTERS
                ],
                "challan_types": [
                    {"key": key, "label": label}
                    for key, label in DeliveryChallan.ChallanType.choices
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "challan_number", "label": "Challan#"},
                    {"key": "customer_name", "label": "Customer Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/delivery-challans/form/",
                "counts": {
                    "all": queryset.count(),
                    "draft": queryset.filter(status=DeliveryChallan.Status.DRAFT).count(),
                    "delivered": queryset.filter(status=DeliveryChallan.Status.DELIVERED).count(),
                    "returned": queryset.filter(status=DeliveryChallan.Status.RETURNED).count(),
                    "cancelled": queryset.filter(status=DeliveryChallan.Status.CANCELLED).count(),
                },
                "actions": [
                    {"key": "save_as_draft", "label": "Save as Draft", "path": "/api/delivery-challans/"},
                    {"key": "save_as_delivered", "label": "Save as Delivered", "path": "/api/delivery-challans/"},
                    {"key": "refresh", "label": "Refresh", "path": "/api/delivery-challans/refresh/"},
                    {"key": "export", "label": "Export Delivery Challans", "path": "/api/delivery-challans/export/"},
                    {"key": "deliver", "label": "Mark as Delivered", "path": "/api/delivery-challans/deliver/"},
                    {"key": "return", "label": "Mark as Returned", "path": "/api/delivery-challans/return/"},
                    {"key": "cancel", "label": "Cancel", "path": "/api/delivery-challans/cancel/"},
                ],
            }
        )


class DeliveryChallanFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = resolve_organization(
            request.user,
            request.query_params.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        data = build_challan_form(request.user, organization)
        challan_id = (
            request.query_params.get("delivery_challan_id")
            or request.query_params.get("id")
        )
        if challan_id:
            parsed_id, error_response = parse_uuid(challan_id, "delivery_challan_id")
            if error_response:
                return error_response
            challan = get_challan_queryset(request.user).filter(pk=parsed_id).first()
            if not challan:
                return api_error(
                    "Delivery challan not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            data["title"] = "Edit Delivery Challan"
            data["delivery_challan"] = DeliveryChallanSerializer(challan).data
        return api_success(data=data)


class DeliveryChallanRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_challan_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=DeliveryChallanSerializer)
        if response is not None:
            response.data["message"] = "Delivery challans refreshed."
            return response
        return api_success(data=[], message="Delivery challans refreshed.")


class DeliveryChallanExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_challan_queryset(request)
        if error_response:
            return error_response
        rows = DeliveryChallanSerializer(queryset, many=True).data
        export_format = (
            request.query_params.get("export_format")
            or request.query_params.get("format")
            or "json"
        ).strip().lower()
        if export_format == "csv":
            import csv
            from io import StringIO

            buffer = StringIO()
            writer = csv.DictWriter(
                buffer,
                fieldnames=[
                    "delivery_challan_id",
                    "challan_number",
                    "customer_name",
                    "challan_date",
                    "challan_type",
                    "status",
                    "total_amount",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "delivery_challan_id": row["delivery_challan_id"],
                        "challan_number": row["challan_number"],
                        "customer_name": row["customer_name"],
                        "challan_date": row["challan_date"],
                        "challan_type": row["challan_type"],
                        "status": row["status"],
                        "total_amount": row["total_amount"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="delivery_challans.csv"'
            return response
        return api_success(
            data={"count": len(rows), "delivery_challans": rows},
            message="Delivery challans exported successfully.",
        )


class DeliveryChallanDeliverView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        challan_id, error_response = get_challan_id_param(request)
        if error_response:
            return error_response
        challan = get_challan_queryset(request.user).filter(pk=challan_id).first()
        if not challan:
            return api_error("Delivery challan not found.", status_code=status.HTTP_404_NOT_FOUND)
        if challan.status in (
            DeliveryChallan.Status.CANCELLED,
            DeliveryChallan.Status.RETURNED,
        ):
            return api_error(
                "Cancelled or returned challans cannot be marked as delivered.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not challan.lines.exists():
            return api_error(
                "Add at least one line item before marking as delivered.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        challan.status = DeliveryChallan.Status.DELIVERED
        if not challan.delivered_at:
            challan.delivered_at = timezone.now()
        challan.save(update_fields=["status", "delivered_at", "updated_at"])
        challan = get_challan_queryset(request.user).get(pk=challan.pk)
        return api_success(
            data=DeliveryChallanSerializer(challan).data,
            message="Delivery challan marked as delivered.",
        )


class DeliveryChallanReturnView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        challan_id, error_response = get_challan_id_param(request)
        if error_response:
            return error_response
        challan = get_challan_queryset(request.user).filter(pk=challan_id).first()
        if not challan:
            return api_error("Delivery challan not found.", status_code=status.HTTP_404_NOT_FOUND)
        if challan.status != DeliveryChallan.Status.DELIVERED:
            return api_error(
                "Only delivered challans can be returned.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        challan.status = DeliveryChallan.Status.RETURNED
        if not challan.returned_at:
            challan.returned_at = timezone.now()
        challan.save(update_fields=["status", "returned_at", "updated_at"])
        challan = get_challan_queryset(request.user).get(pk=challan.pk)
        return api_success(
            data=DeliveryChallanSerializer(challan).data,
            message="Delivery challan marked as returned.",
        )


class DeliveryChallanCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        challan_id, error_response = get_challan_id_param(request)
        if error_response:
            return error_response
        challan = get_challan_queryset(request.user).filter(pk=challan_id).first()
        if not challan:
            return api_error("Delivery challan not found.", status_code=status.HTTP_404_NOT_FOUND)
        if challan.status in (
            DeliveryChallan.Status.RETURNED,
            DeliveryChallan.Status.CANCELLED,
        ):
            return api_error(
                "This delivery challan cannot be cancelled.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        challan.status = DeliveryChallan.Status.CANCELLED
        if not challan.cancelled_at:
            challan.cancelled_at = timezone.now()
        challan.save(update_fields=["status", "cancelled_at", "updated_at"])
        challan = get_challan_queryset(request.user).get(pk=challan.pk)
        return api_success(
            data=DeliveryChallanSerializer(challan).data,
            message="Delivery challan cancelled successfully.",
        )
