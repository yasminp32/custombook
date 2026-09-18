from datetime import date
from uuid import UUID

from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as SerializerValidationError
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.payments_made.filters import (
    PAYMENT_MODE_FILTERS,
    PAYMENT_TAB_FILTERS,
    PaymentMadeFilter,
)
from apps.payments_made.models import PaymentMade
from apps.payments_made.serializers import (
    PaymentMadeSerializer,
    PaymentMadeWriteSerializer,
    next_payment_number,
)
from apps.vendors.models import Vendor

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "payment_date",
    "payment_date": "payment_date",
    "payment_number": "payment_number",
    "payment#": "payment_number",
    "vendor_name": "vendor__display_name",
    "amount": "amount",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_payment_queryset(user):
    return PaymentMade.objects.filter(organization__owner=user).select_related(
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


def get_payment_id_param(request):
    payment_id = (
        request.query_params.get("payment_id")
        or request.query_params.get("id")
        or request.data.get("payment_id")
        or request.data.get("id")
    )
    if not payment_id:
        return None, api_error(
            "payment_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(payment_id, "payment_id")


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


def filtered_payment_queryset(request):
    queryset = get_payment_queryset(request.user)
    payment_filter = PaymentMadeFilter(request.query_params, queryset=queryset)
    if not payment_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=payment_filter.errors)
    queryset, error_response = apply_sorting(payment_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def payment_counts(queryset):
    today = date.today()
    return {
        "all": queryset.count(),
        "this_month": queryset.filter(
            payment_date__year=today.year,
            payment_date__month=today.month,
        ).count(),
    }


def vendor_option(vendor):
    name = vendor.display_name or vendor.company_name or ""
    return {
        "vendor_id": vendor.id,
        "display_name": name,
        "company_name": vendor.company_name or "",
        "initials": (name[:1] or "").upper(),
    }


def build_payment_form(user, organization):
    queryset = get_payment_queryset(user)
    vendors = Vendor.objects.filter(
        organization=organization,
        status=Vendor.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    today = date.today()
    next_number = next_payment_number(organization)
    currency = (organization.currency if organization else "INR") or "INR"
    return {
        "title": "New Payment",
        "next_payment_number": next_number,
        "defaults": {
            "payment_number": next_number,
            "payment_date": today.isoformat(),
            "payment_date_label": today.strftime("%d %b %Y"),
            "payment_mode": PaymentMade.PaymentMode.BANK_TRANSFER,
            "reference_number": "",
            "amount": "0.00",
            "currency": currency,
            "action": "save",
        },
        "fields": {
            "vendor_id": {
                "label": "Vendor",
                "required": True,
                "placeholder": "Select a vendor",
            },
            "payment_number": {"label": "Payment#", "required": True},
            "payment_date": {"label": "Payment Date", "required": True},
            "payment_mode": {"label": "Payment Mode", "required": False},
            "reference_number": {"label": "Reference#", "required": False},
            "amount": {"label": "Amount", "required": True},
        },
        "vendors": [vendor_option(row) for row in vendors],
        "payment_modes": [
            {"key": key, "label": label} for key, label in PaymentMade.PaymentMode.choices
        ],
        "counts": payment_counts(queryset),
        "actions": [
            {"key": "save", "label": "Save", "path": "/api/payments-made/"},
        ],
        "create_path": "/api/payments-made/",
        "export_path": "/api/payments-made/export/",
        "refresh_path": "/api/payments-made/refresh/",
    }


class PaymentMadeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment_id = request.query_params.get("payment_id") or request.query_params.get("id")
        if payment_id:
            parsed_id, error_response = parse_uuid(payment_id, "payment_id")
            if error_response:
                return error_response
            payment = get_payment_queryset(request.user).filter(pk=parsed_id).first()
            if not payment:
                return api_error("Payment not found.", status_code=status.HTTP_404_NOT_FOUND)
            return api_success(data=PaymentMadeSerializer(payment).data)

        queryset, error_response = filtered_payment_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=PaymentMadeSerializer)
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
                "Organization not found. Complete organization setup before recording payments.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PaymentMadeWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            payment = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Payment number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        payment = get_payment_queryset(request.user).get(pk=payment.pk)
        return api_success(
            data=PaymentMadeSerializer(payment).data,
            message="Payment recorded.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        payment_id, error_response = get_payment_id_param(request)
        if error_response:
            return error_response
        payment = get_payment_queryset(request.user).filter(pk=payment_id).first()
        if not payment:
            return api_error("Payment not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = PaymentMadeWriteSerializer(payment, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            payment = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Payment number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        payment = get_payment_queryset(request.user).get(pk=payment.pk)
        return api_success(
            data=PaymentMadeSerializer(payment).data,
            message="Payment updated successfully.",
        )

    def delete(self, request):
        payment_id, error_response = get_payment_id_param(request)
        if error_response:
            return error_response
        payment = get_payment_queryset(request.user).filter(pk=payment_id).first()
        if not payment:
            return api_error("Payment not found.", status_code=status.HTTP_404_NOT_FOUND)
        payment.delete()
        return api_success(message="Payment deleted successfully.")


class PaymentMadeOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_payment_queryset(request.user)
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in PAYMENT_TAB_FILTERS],
                "modes": [{"key": key, "label": label} for key, label in PAYMENT_MODE_FILTERS],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "payment_number", "label": "Payment#"},
                    {"key": "vendor_name", "label": "Vendor Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/payments-made/form/",
                "counts": payment_counts(queryset),
                "empty_state": {
                    "title": "No payments found",
                    "message": "Tap the + button to record a payment made.",
                },
                "actions": [
                    {"key": "save", "label": "Save", "path": "/api/payments-made/"},
                    {
                        "key": "export",
                        "label": "Export Payments Made",
                        "description": "Export the current payment list",
                        "path": "/api/payments-made/export/",
                    },
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "description": "Reload the latest payments made",
                        "path": "/api/payments-made/refresh/",
                    },
                ],
            }
        )


class PaymentMadeFormView(APIView):
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
        data = build_payment_form(request.user, organization)
        payment_id = request.query_params.get("payment_id") or request.query_params.get("id")
        if payment_id:
            parsed_id, error_response = parse_uuid(payment_id, "payment_id")
            if error_response:
                return error_response
            payment = get_payment_queryset(request.user).filter(pk=parsed_id).first()
            if not payment:
                return api_error("Payment not found.", status_code=status.HTTP_404_NOT_FOUND)
            data["title"] = "Edit Payment"
            data["payment"] = PaymentMadeSerializer(payment).data
        return api_success(data=data)


class PaymentMadeRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_payment_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=PaymentMadeSerializer)
        if response is not None:
            response.data["message"] = "Payments refreshed."
            return response
        return api_success(data=[], message="Payments refreshed.")


class PaymentMadeExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_payment_queryset(request)
        if error_response:
            return error_response
        rows = PaymentMadeSerializer(queryset, many=True).data
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
                    "payment_id",
                    "payment_number",
                    "vendor_name",
                    "payment_date",
                    "payment_mode",
                    "reference_number",
                    "amount",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "payment_id": row["payment_id"],
                        "payment_number": row["payment_number"],
                        "vendor_name": row["vendor_name"],
                        "payment_date": row["payment_date"],
                        "payment_mode": row["payment_mode"],
                        "reference_number": row["reference_number"],
                        "amount": row["amount"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="payments_made.csv"'
            return response
        return api_success(
            data={"count": len(rows), "payments": rows},
            message="Payments exported successfully.",
        )
