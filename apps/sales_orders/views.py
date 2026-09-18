from uuid import UUID

from datetime import date

from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as SerializerValidationError
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.customers.constants import PAYMENT_TERMS
from apps.customers.models import Customer
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.sales_orders.filters import (
    SALES_ORDER_STATUS_FILTERS,
    SALES_ORDER_TAB_FILTERS,
    SalesOrderFilter,
)
from apps.sales_orders.models import SalesOrder
from apps.sales_orders.serializers import (
    SalesOrderSerializer,
    SalesOrderWriteSerializer,
    next_sales_order_number,
)

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "order_date",
    "order_date": "order_date",
    "sales_order_number": "sales_order_number",
    "sales_order#": "sales_order_number",
    "reference_number": "reference_number",
    "reference#": "reference_number",
    "customer_name": "customer__display_name",
    "amount": "total_amount",
    "total_amount": "total_amount",
}


DEFAULT_DELIVERY_METHODS = (
    "Air Freight",
    "Sea Freight",
    "Road Transport",
    "Courier",
    "Hand Delivery",
)


def customer_option(customer):
    return {
        "customer_id": customer.id,
        "display_name": customer.display_name or customer.company_name or customer.name,
        "company_name": customer.company_name or "",
        "payment_terms": customer.payment_terms or "due_on_receipt",
        "currency": customer.currency or "INR",
    }


def item_option(item):
    price = item.selling_price
    return {
        "item_id": item.id,
        "name": item.name,
        "sku": item.sku or "",
        "selling_price": f"{price:.2f}" if price is not None else "0.00",
        "tax": item.tax or "",
        "unit": item.unit or "",
    }


def salesperson_options(organization, queryset):
    rows = []
    seen = set()
    owner = organization.owner if organization else None
    if owner:
        name = (
            f"{owner.first_name} {owner.last_name}".strip()
            or owner.email
        )
        rows.append(
            {
                "salesperson_id": owner.id,
                "salesperson_name": name,
            }
        )
        seen.add(str(owner.id))
    for salesperson_id, salesperson_name in (
        queryset.exclude(salesperson_name="")
        .values_list("salesperson_id", "salesperson_name")
        .distinct()
    ):
        key = str(salesperson_id or salesperson_name)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "salesperson_id": salesperson_id,
                "salesperson_name": salesperson_name,
            }
        )
    return rows


def delivery_method_options(queryset):
    custom = [
        value
        for value in queryset.exclude(delivery_method="")
        .values_list("delivery_method", flat=True)
        .distinct()
        if value
    ]
    merged = list(DEFAULT_DELIVERY_METHODS)
    for value in custom:
        if value not in merged:
            merged.append(value)
    return [{"key": value, "label": value} for value in merged]


def build_new_sales_order_form(user, organization):
    queryset = get_sales_order_queryset(user)
    customers = Customer.objects.filter(
        organization=organization,
        status=Customer.Status.ACTIVE,
    ).order_by(
        "display_name",
        "company_name",
    )[:100]
    items = Item.objects.filter(
        organization=organization,
        sales_enabled=True,
        status=Item.Status.ACTIVE,
    ).order_by(
        "name"
    )[:100]
    today = date.today()
    next_number = next_sales_order_number(organization)
    return {
        "title": "New Sales Order",
        "next_sales_order_number": next_number,
        "defaults": {
            "sales_order_number": next_number,
            "order_date": today.isoformat(),
            "order_date_label": today.strftime("%d %b %Y"),
            "expected_shipment_date": None,
            "payment_terms": "due_on_receipt",
            "delivery_method": "",
            "tax_type": SalesOrder.TaxType.EXCLUSIVE,
            "customer_notes": "Looking forward for your business.",
            "terms_and_conditions": "",
            "action": "save_as_draft",
        },
        "fields": {
            "customer_id": {
                "label": "Customer Name",
                "required": True,
                "placeholder": "Start typing to select a Customer",
                "can_add": True,
                "add_path": "/api/customers/",
            },
            "sales_order_number": {
                "label": "Sales Order#",
                "required": True,
            },
            "reference_number": {"label": "Reference#", "required": False},
            "order_date": {"label": "Sales Order Date", "required": True},
            "expected_shipment_date": {
                "label": "Expected Shipment Date",
                "required": False,
            },
            "payment_terms": {"label": "Payment Terms", "required": False},
            "delivery_method": {
                "label": "Delivery Method",
                "required": False,
                "placeholder": "Select or Type to add",
            },
            "salesperson": {
                "label": "Salesperson",
                "required": False,
                "placeholder": "Select or Add Salesperson",
            },
            "tax_type": {"label": "Tax", "required": False},
            "line_items": {"label": "Add Line Item", "required": False},
            "customer_notes": {"label": "Customer Notes", "required": False},
            "terms_and_conditions": {
                "label": "Terms & Conditions",
                "required": False,
            },
            "attachments": {
                "label": "Attachments",
                "upload_path": "/api/attachments/",
            },
        },
        "customers": [customer_option(row) for row in customers],
        "items": [item_option(row) for row in items],
        "payment_terms": [
            {"key": key, "label": label} for key, label in PAYMENT_TERMS
        ],
        "delivery_methods": delivery_method_options(queryset),
        "salespersons": salesperson_options(organization, queryset),
        "tax_types": [
            {"key": key, "label": label} for key, label in SalesOrder.TaxType.choices
        ],
        "actions": [
            {
                "key": "save_as_draft",
                "label": "Save as Draft",
                "path": "/api/sales-orders/",
            },
            {
                "key": "save_as_confirmed",
                "label": "Save as Confirmed",
                "path": "/api/sales-orders/",
            },
        ],
        "attachments_path": "/api/attachments/",
        "create_path": "/api/sales-orders/",
    }


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_sales_order_queryset(user):
    return SalesOrder.objects.filter(organization__owner=user).select_related(
        "organization",
        "customer",
        "quote",
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


def get_sales_order_id_param(request):
    sales_order_id = (
        request.query_params.get("sales_order_id")
        or request.query_params.get("id")
        or request.data.get("sales_order_id")
        or request.data.get("id")
    )
    if not sales_order_id:
        return None, api_error(
            "sales_order_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(sales_order_id, "sales_order_id")


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


def filtered_sales_order_queryset(request):
    queryset = get_sales_order_queryset(request.user)
    sales_order_filter = SalesOrderFilter(request.query_params, queryset=queryset)
    if not sales_order_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=sales_order_filter.errors)
    queryset, error_response = apply_sorting(sales_order_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


class SalesOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sales_order_id = request.query_params.get("sales_order_id") or request.query_params.get("id")
        if sales_order_id:
            parsed_id, error_response = parse_uuid(sales_order_id, "sales_order_id")
            if error_response:
                return error_response
            sales_order = get_sales_order_queryset(request.user).filter(pk=parsed_id).first()
            if not sales_order:
                return api_error(
                    "Sales order not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return api_success(data=SalesOrderSerializer(sales_order).data)

        queryset, error_response = filtered_sales_order_queryset(request)
        if error_response:
            return error_response

        response = paginate_queryset(request, queryset, serializer=SalesOrderSerializer)
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
                "Organization not found. Complete organization setup before creating sales orders.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SalesOrderWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            sales_order = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Sales order number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        sales_order = get_sales_order_queryset(request.user).get(pk=sales_order.pk)
        if sales_order.status == SalesOrder.Status.CONFIRMED:
            message = "Sales order confirmed successfully."
        else:
            message = "Sales order saved as draft."
        return api_success(
            data=SalesOrderSerializer(sales_order).data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        sales_order_id, error_response = get_sales_order_id_param(request)
        if error_response:
            return error_response
        sales_order = get_sales_order_queryset(request.user).filter(pk=sales_order_id).first()
        if not sales_order:
            return api_error("Sales order not found.", status_code=status.HTTP_404_NOT_FOUND)

        serializer = SalesOrderWriteSerializer(sales_order, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            sales_order = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Sales order number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        sales_order = get_sales_order_queryset(request.user).get(pk=sales_order.pk)
        return api_success(
            data=SalesOrderSerializer(sales_order).data,
            message="Sales order updated successfully.",
        )

    def patch(self, request):
        sales_order_id, error_response = get_sales_order_id_param(request)
        if error_response:
            return error_response
        sales_order = get_sales_order_queryset(request.user).filter(pk=sales_order_id).first()
        if not sales_order:
            return api_error("Sales order not found.", status_code=status.HTTP_404_NOT_FOUND)

        serializer = SalesOrderWriteSerializer(sales_order, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            sales_order = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Sales order number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        sales_order = get_sales_order_queryset(request.user).get(pk=sales_order.pk)
        return api_success(
            data=SalesOrderSerializer(sales_order).data,
            message="Sales order updated successfully.",
        )

    def delete(self, request):
        sales_order_id, error_response = get_sales_order_id_param(request)
        if error_response:
            return error_response
        sales_order = get_sales_order_queryset(request.user).filter(pk=sales_order_id).first()
        if not sales_order:
            return api_error("Sales order not found.", status_code=status.HTTP_404_NOT_FOUND)
        if sales_order.status == SalesOrder.Status.INVOICED:
            return api_error(
                "Invoiced sales orders cannot be deleted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        sales_order.delete()
        return api_success(message="Sales order deleted successfully.")


class SalesOrderOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_sales_order_queryset(request.user)
        return api_success(
            data={
                "tabs": [
                    {"key": key, "label": label} for key, label in SALES_ORDER_TAB_FILTERS
                ],
                "statuses": [
                    {"key": key, "label": label}
                    for key, label in SALES_ORDER_STATUS_FILTERS
                ],
                "tax_types": [
                    {"key": key, "label": label} for key, label in SalesOrder.TaxType.choices
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "sales_order_number", "label": "Sales Order#"},
                    {"key": "reference_number", "label": "Reference#"},
                    {"key": "customer_name", "label": "Customer Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "payment_terms": [
                    {"key": key, "label": label} for key, label in PAYMENT_TERMS
                ],
                "form_path": "/api/sales-orders/form/",
                "counts": {
                    "all": queryset.count(),
                    "draft": queryset.filter(status=SalesOrder.Status.DRAFT).count(),
                    "confirmed": queryset.filter(status=SalesOrder.Status.CONFIRMED).count(),
                    "invoiced": queryset.filter(status=SalesOrder.Status.INVOICED).count(),
                    "cancelled": queryset.filter(status=SalesOrder.Status.CANCELLED).count(),
                },
                "actions": [
                    {
                        "key": "save_as_draft",
                        "label": "Save as Draft",
                        "path": "/api/sales-orders/",
                    },
                    {
                        "key": "save_and_confirm",
                        "label": "Save and Confirm",
                        "path": "/api/sales-orders/",
                    },
                    {
                        "key": "save_as_confirmed",
                        "label": "Save as Confirmed",
                        "path": "/api/sales-orders/",
                    },
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "path": "/api/sales-orders/refresh/",
                    },
                    {
                        "key": "export",
                        "label": "Export Sales Orders",
                        "path": "/api/sales-orders/export/",
                    },
                    {
                        "key": "confirm",
                        "label": "Confirm",
                        "path": "/api/sales-orders/confirm/",
                    },
                    {
                        "key": "cancel",
                        "label": "Cancel",
                        "path": "/api/sales-orders/cancel/",
                    },
                    {
                        "key": "mark_invoiced",
                        "label": "Mark as Invoiced",
                        "path": "/api/sales-orders/mark-invoiced/",
                    },
                ],
            }
        )


class SalesOrderFormView(APIView):
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

        data = build_new_sales_order_form(request.user, organization)
        sales_order_id = (
            request.query_params.get("sales_order_id")
            or request.query_params.get("id")
        )
        if sales_order_id:
            parsed_id, error_response = parse_uuid(sales_order_id, "sales_order_id")
            if error_response:
                return error_response
            sales_order = get_sales_order_queryset(request.user).filter(pk=parsed_id).first()
            if not sales_order:
                return api_error(
                    "Sales order not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            data["title"] = "Edit Sales Order"
            data["sales_order"] = SalesOrderSerializer(sales_order).data
        return api_success(data=data)


class SalesOrderRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_sales_order_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=SalesOrderSerializer)
        if response is not None:
            response.data["message"] = "Sales orders refreshed."
            return response
        return api_success(data=[], message="Sales orders refreshed.")


class SalesOrderExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_sales_order_queryset(request)
        if error_response:
            return error_response
        rows = SalesOrderSerializer(queryset, many=True).data
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
                    "sales_order_id",
                    "sales_order_number",
                    "reference_number",
                    "customer_name",
                    "order_date",
                    "status",
                    "total_amount",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "sales_order_id": row["sales_order_id"],
                        "sales_order_number": row["sales_order_number"],
                        "reference_number": row["reference_number"],
                        "customer_name": row["customer_name"],
                        "order_date": row["order_date"],
                        "status": row["status"],
                        "total_amount": row["total_amount"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="sales_orders.csv"'
            return response
        return api_success(
            data={"count": len(rows), "sales_orders": rows},
            message="Sales orders exported successfully.",
        )


class SalesOrderConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sales_order_id, error_response = get_sales_order_id_param(request)
        if error_response:
            return error_response
        sales_order = get_sales_order_queryset(request.user).filter(pk=sales_order_id).first()
        if not sales_order:
            return api_error("Sales order not found.", status_code=status.HTTP_404_NOT_FOUND)
        if sales_order.status == SalesOrder.Status.CANCELLED:
            return api_error(
                "Cancelled sales orders cannot be confirmed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if sales_order.status == SalesOrder.Status.INVOICED:
            return api_error(
                "Invoiced sales orders are already confirmed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not sales_order.lines.exists():
            return api_error(
                "Add at least one line item before confirming a sales order.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        sales_order.status = SalesOrder.Status.CONFIRMED
        if not sales_order.confirmed_at:
            sales_order.confirmed_at = timezone.now()
        sales_order.save(update_fields=["status", "confirmed_at", "updated_at"])
        sales_order = get_sales_order_queryset(request.user).get(pk=sales_order.pk)
        return api_success(
            data=SalesOrderSerializer(sales_order).data,
            message="Sales order confirmed successfully.",
        )


class SalesOrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sales_order_id, error_response = get_sales_order_id_param(request)
        if error_response:
            return error_response
        sales_order = get_sales_order_queryset(request.user).filter(pk=sales_order_id).first()
        if not sales_order:
            return api_error("Sales order not found.", status_code=status.HTTP_404_NOT_FOUND)
        if sales_order.status == SalesOrder.Status.INVOICED:
            return api_error(
                "Invoiced sales orders cannot be cancelled.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if sales_order.status == SalesOrder.Status.CANCELLED:
            return api_error(
                "Sales order is already cancelled.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        sales_order.status = SalesOrder.Status.CANCELLED
        if not sales_order.cancelled_at:
            sales_order.cancelled_at = timezone.now()
        sales_order.save(update_fields=["status", "cancelled_at", "updated_at"])
        sales_order = get_sales_order_queryset(request.user).get(pk=sales_order.pk)
        return api_success(
            data=SalesOrderSerializer(sales_order).data,
            message="Sales order cancelled successfully.",
        )


class SalesOrderMarkInvoicedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sales_order_id, error_response = get_sales_order_id_param(request)
        if error_response:
            return error_response
        sales_order = get_sales_order_queryset(request.user).filter(pk=sales_order_id).first()
        if not sales_order:
            return api_error("Sales order not found.", status_code=status.HTTP_404_NOT_FOUND)
        if sales_order.status == SalesOrder.Status.CANCELLED:
            return api_error(
                "Cancelled sales orders cannot be invoiced.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if sales_order.status == SalesOrder.Status.DRAFT:
            return api_error(
                "Confirm the sales order before marking it as invoiced.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        sales_order.status = SalesOrder.Status.INVOICED
        if not sales_order.invoiced_at:
            sales_order.invoiced_at = timezone.now()
        sales_order.save(update_fields=["status", "invoiced_at", "updated_at"])
        sales_order = get_sales_order_queryset(request.user).get(pk=sales_order.pk)
        return api_success(
            data=SalesOrderSerializer(sales_order).data,
            message="Sales order marked as invoiced.",
        )
