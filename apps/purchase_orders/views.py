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
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.purchase_orders.filters import (
    PURCHASE_ORDER_STATUS_FILTERS,
    PURCHASE_ORDER_TAB_FILTERS,
    PurchaseOrderFilter,
)
from apps.purchase_orders.models import PurchaseOrder
from apps.purchase_orders.serializers import (
    PurchaseOrderSerializer,
    PurchaseOrderWriteSerializer,
    next_purchase_order_number,
)
from apps.vendors.models import Vendor

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "order_date",
    "order_date": "order_date",
    "purchase_order_number": "purchase_order_number",
    "purchase_order#": "purchase_order_number",
    "vendor_name": "vendor__display_name",
    "amount": "amount",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_purchase_order_queryset(user):
    return PurchaseOrder.objects.filter(organization__owner=user).select_related(
        "organization",
        "vendor",
        "created_by",
    )


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


def get_purchase_order_id_param(request):
    purchase_order_id = (
        request.query_params.get("purchase_order_id")
        or request.query_params.get("id")
        or request.data.get("purchase_order_id")
        or request.data.get("id")
    )
    if not purchase_order_id:
        return None, api_error(
            "purchase_order_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(purchase_order_id, "purchase_order_id")


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


def filtered_purchase_order_queryset(request):
    queryset = get_purchase_order_queryset(request.user)
    purchase_order_filter = PurchaseOrderFilter(request.query_params, queryset=queryset)
    if not purchase_order_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=purchase_order_filter.errors)
    queryset, error_response = apply_sorting(purchase_order_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def purchase_order_counts(queryset):
    return {
        "all": queryset.count(),
        "draft": queryset.filter(status=PurchaseOrder.Status.DRAFT).count(),
        "issued": queryset.filter(status=PurchaseOrder.Status.ISSUED).count(),
        "billed": queryset.filter(status=PurchaseOrder.Status.BILLED).count(),
        "cancelled": queryset.filter(status=PurchaseOrder.Status.CANCELLED).count(),
    }


def vendor_option(vendor):
    name = vendor.display_name or vendor.company_name or ""
    return {
        "vendor_id": vendor.id,
        "display_name": name,
        "company_name": vendor.company_name or "",
        "initials": (name[:1] or "").upper(),
    }


def success_message(purchase_order):
    if purchase_order.status == PurchaseOrder.Status.ISSUED:
        return "Purchase order saved as issued."
    if purchase_order.status == PurchaseOrder.Status.BILLED:
        return "Purchase order marked as billed."
    if purchase_order.status == PurchaseOrder.Status.CANCELLED:
        return "Purchase order cancelled."
    return "Purchase order saved as draft."


def build_purchase_order_form(user, organization):
    queryset = get_purchase_order_queryset(user)
    vendors = Vendor.objects.filter(
        organization=organization,
        status=Vendor.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    today = date.today()
    next_number = next_purchase_order_number(organization)
    currency = (organization.currency if organization else "INR") or "INR"
    return {
        "title": "New Purchase Order",
        "next_purchase_order_number": next_number,
        "defaults": {
            "purchase_order_number": next_number,
            "order_date": today.isoformat(),
            "order_date_label": today.strftime("%d %b %Y"),
            "expected_delivery_date": None,
            "reference_number": "",
            "amount": "0.00",
            "currency": currency,
            "status": PurchaseOrder.Status.DRAFT,
            "action": "save_as_draft",
        },
        "fields": {
            "vendor_id": {
                "label": "Vendor",
                "required": True,
                "placeholder": "Select a vendor",
            },
            "purchase_order_number": {
                "label": "Purchase Order#",
                "required": True,
            },
            "reference_number": {
                "label": "Reference#",
                "required": False,
            },
            "order_date": {
                "label": "Order Date",
                "required": True,
            },
            "expected_delivery_date": {
                "label": "Expected Delivery Date",
                "required": False,
                "placeholder": "dd MMM yyyy",
            },
            "amount": {
                "label": "Amount",
                "required": True,
            },
        },
        "vendors": [vendor_option(row) for row in vendors],
        "counts": purchase_order_counts(queryset),
        "actions": [
            {
                "key": "save_as_draft",
                "label": "Save as Draft",
                "path": "/api/purchase-orders/",
            },
            {
                "key": "save_as_issued",
                "label": "Save as Issued",
                "path": "/api/purchase-orders/",
            },
        ],
        "create_path": "/api/purchase-orders/",
        "export_path": "/api/purchase-orders/export/",
        "refresh_path": "/api/purchase-orders/refresh/",
    }


class PurchaseOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        purchase_order_id = (
            request.query_params.get("purchase_order_id")
            or request.query_params.get("id")
        )
        if purchase_order_id:
            parsed_id, error_response = parse_uuid(purchase_order_id, "purchase_order_id")
            if error_response:
                return error_response
            purchase_order = (
                get_purchase_order_queryset(request.user).filter(pk=parsed_id).first()
            )
            if not purchase_order:
                return api_error(
                    "Purchase order not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return api_success(data=PurchaseOrderSerializer(purchase_order).data)

        queryset, error_response = filtered_purchase_order_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=PurchaseOrderSerializer)
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
                "Organization not found. Complete organization setup before creating purchase orders.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PurchaseOrderWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            purchase_order = serializer.save(
                organization=organization,
                created_by=request.user,
            )
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Purchase order number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        purchase_order = get_purchase_order_queryset(request.user).get(pk=purchase_order.pk)
        return api_success(
            data=PurchaseOrderSerializer(purchase_order).data,
            message=success_message(purchase_order),
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        purchase_order_id, error_response = get_purchase_order_id_param(request)
        if error_response:
            return error_response
        purchase_order = (
            get_purchase_order_queryset(request.user).filter(pk=purchase_order_id).first()
        )
        if not purchase_order:
            return api_error("Purchase order not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = PurchaseOrderWriteSerializer(
            purchase_order,
            data=request.data,
            partial=partial,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            purchase_order = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Purchase order number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        purchase_order = get_purchase_order_queryset(request.user).get(pk=purchase_order.pk)
        return api_success(
            data=PurchaseOrderSerializer(purchase_order).data,
            message="Purchase order updated successfully.",
        )

    def delete(self, request):
        purchase_order_id, error_response = get_purchase_order_id_param(request)
        if error_response:
            return error_response
        purchase_order = (
            get_purchase_order_queryset(request.user).filter(pk=purchase_order_id).first()
        )
        if not purchase_order:
            return api_error("Purchase order not found.", status_code=status.HTTP_404_NOT_FOUND)
        if purchase_order.status in (
            PurchaseOrder.Status.ISSUED,
            PurchaseOrder.Status.BILLED,
        ):
            return api_error(
                "Issued or billed purchase orders cannot be deleted. Cancel them instead.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        purchase_order.delete()
        return api_success(message="Purchase order deleted successfully.")


class PurchaseOrderOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_purchase_order_queryset(request.user)
        return api_success(
            data={
                "tabs": [
                    {"key": key, "label": label} for key, label in PURCHASE_ORDER_TAB_FILTERS
                ],
                "statuses": [
                    {"key": key, "label": label} for key, label in PURCHASE_ORDER_STATUS_FILTERS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "purchase_order_number", "label": "Purchase Order#"},
                    {"key": "vendor_name", "label": "Vendor Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/purchase-orders/form/",
                "counts": purchase_order_counts(queryset),
                "actions": [
                    {
                        "key": "save_as_draft",
                        "label": "Save as Draft",
                        "path": "/api/purchase-orders/",
                    },
                    {
                        "key": "save_as_issued",
                        "label": "Save as Issued",
                        "path": "/api/purchase-orders/",
                    },
                    {
                        "key": "export",
                        "label": "Export Purchase Orders",
                        "path": "/api/purchase-orders/export/",
                    },
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "path": "/api/purchase-orders/refresh/",
                    },
                    {
                        "key": "mark_as_billed",
                        "label": "Mark as Billed",
                        "path": "/api/purchase-orders/mark-billed/",
                    },
                    {
                        "key": "cancel",
                        "label": "Cancel",
                        "path": "/api/purchase-orders/cancel/",
                    },
                ],
            }
        )


class PurchaseOrderFormView(APIView):
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
        data = build_purchase_order_form(request.user, organization)
        purchase_order_id = (
            request.query_params.get("purchase_order_id")
            or request.query_params.get("id")
        )
        if purchase_order_id:
            parsed_id, error_response = parse_uuid(purchase_order_id, "purchase_order_id")
            if error_response:
                return error_response
            purchase_order = (
                get_purchase_order_queryset(request.user).filter(pk=parsed_id).first()
            )
            if not purchase_order:
                return api_error(
                    "Purchase order not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            data["title"] = "Edit Purchase Order"
            data["purchase_order"] = PurchaseOrderSerializer(purchase_order).data
        return api_success(data=data)


class PurchaseOrderRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_purchase_order_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=PurchaseOrderSerializer)
        if response is not None:
            response.data["message"] = "Purchase orders refreshed."
            return response
        return api_success(data=[], message="Purchase orders refreshed.")


class PurchaseOrderExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_purchase_order_queryset(request)
        if error_response:
            return error_response
        rows = PurchaseOrderSerializer(queryset, many=True).data
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
                    "purchase_order_id",
                    "purchase_order_number",
                    "vendor_name",
                    "order_date",
                    "expected_delivery_date",
                    "status",
                    "amount",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "purchase_order_id": row["purchase_order_id"],
                        "purchase_order_number": row["purchase_order_number"],
                        "vendor_name": row["vendor_name"],
                        "order_date": row["order_date"],
                        "expected_delivery_date": row["expected_delivery_date"],
                        "status": row["status"],
                        "amount": row["amount"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="purchase_orders.csv"'
            return response
        return api_success(
            data={"count": len(rows), "purchase_orders": rows},
            message="Purchase orders exported successfully.",
        )


class PurchaseOrderMarkBilledView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        purchase_order_id, error_response = get_purchase_order_id_param(request)
        if error_response:
            return error_response
        purchase_order = (
            get_purchase_order_queryset(request.user).filter(pk=purchase_order_id).first()
        )
        if not purchase_order:
            return api_error("Purchase order not found.", status_code=status.HTTP_404_NOT_FOUND)
        if purchase_order.status != PurchaseOrder.Status.ISSUED:
            return api_error(
                "Only issued purchase orders can be marked as billed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        purchase_order.status = PurchaseOrder.Status.BILLED
        if not purchase_order.billed_at:
            purchase_order.billed_at = timezone.now()
        purchase_order.save(update_fields=["status", "billed_at", "updated_at"])
        purchase_order = get_purchase_order_queryset(request.user).get(pk=purchase_order.pk)
        return api_success(
            data=PurchaseOrderSerializer(purchase_order).data,
            message="Purchase order marked as billed.",
        )


class PurchaseOrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        purchase_order_id, error_response = get_purchase_order_id_param(request)
        if error_response:
            return error_response
        purchase_order = (
            get_purchase_order_queryset(request.user).filter(pk=purchase_order_id).first()
        )
        if not purchase_order:
            return api_error("Purchase order not found.", status_code=status.HTTP_404_NOT_FOUND)
        if purchase_order.status in (
            PurchaseOrder.Status.BILLED,
            PurchaseOrder.Status.CANCELLED,
        ):
            return api_error(
                "This purchase order cannot be cancelled.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        purchase_order.status = PurchaseOrder.Status.CANCELLED
        if not purchase_order.cancelled_at:
            purchase_order.cancelled_at = timezone.now()
        purchase_order.save(update_fields=["status", "cancelled_at", "updated_at"])
        purchase_order = get_purchase_order_queryset(request.user).get(pk=purchase_order.pk)
        return api_success(
            data=PurchaseOrderSerializer(purchase_order).data,
            message="Purchase order cancelled.",
        )
