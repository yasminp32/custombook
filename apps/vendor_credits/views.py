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
from apps.vendor_credits.filters import (
    VENDOR_CREDIT_STATUS_FILTERS,
    VENDOR_CREDIT_TAB_FILTERS,
    VendorCreditFilter,
)
from apps.vendor_credits.models import VendorCredit
from apps.vendor_credits.serializers import (
    VendorCreditSerializer,
    VendorCreditWriteSerializer,
    next_credit_note_number,
)
from apps.vendors.models import Vendor

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "credit_date",
    "credit_date": "credit_date",
    "credit_note_number": "credit_note_number",
    "credit_note#": "credit_note_number",
    "vendor_name": "vendor__display_name",
    "amount": "amount",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_vendor_credit_queryset(user):
    return VendorCredit.objects.filter(organization__owner=user).select_related(
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


def get_vendor_credit_id_param(request):
    vendor_credit_id = (
        request.query_params.get("vendor_credit_id")
        or request.query_params.get("credit_note_id")
        or request.query_params.get("id")
        or request.data.get("vendor_credit_id")
        or request.data.get("credit_note_id")
        or request.data.get("id")
    )
    if not vendor_credit_id:
        return None, api_error(
            "vendor_credit_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(vendor_credit_id, "vendor_credit_id")


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


def filtered_vendor_credit_queryset(request):
    queryset = get_vendor_credit_queryset(request.user)
    credit_filter = VendorCreditFilter(request.query_params, queryset=queryset)
    if not credit_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=credit_filter.errors)
    queryset, error_response = apply_sorting(credit_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def vendor_credit_counts(queryset):
    return {
        "all": queryset.count(),
        "open": queryset.filter(status=VendorCredit.Status.OPEN).count(),
        "closed": queryset.filter(status=VendorCredit.Status.CLOSED).count(),
        "draft": queryset.filter(status=VendorCredit.Status.DRAFT).count(),
        "void": queryset.filter(status=VendorCredit.Status.VOID).count(),
    }


def vendor_option(vendor):
    name = vendor.display_name or vendor.company_name or ""
    return {
        "vendor_id": vendor.id,
        "display_name": name,
        "company_name": vendor.company_name or "",
        "initials": (name[:1] or "").upper(),
    }


def success_message(vendor_credit):
    if vendor_credit.status == VendorCredit.Status.OPEN:
        return "Vendor credit saved as open."
    if vendor_credit.status == VendorCredit.Status.CLOSED:
        return "Vendor credit closed."
    if vendor_credit.status == VendorCredit.Status.VOID:
        return "Vendor credit voided."
    return "Vendor credit saved as draft."


def build_vendor_credit_form(user, organization):
    queryset = get_vendor_credit_queryset(user)
    vendors = Vendor.objects.filter(
        organization=organization,
        status=Vendor.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    today = date.today()
    next_number = next_credit_note_number(organization)
    currency = (organization.currency if organization else "INR") or "INR"
    return {
        "title": "New Vendor Credit",
        "next_credit_note_number": next_number,
        "defaults": {
            "credit_note_number": next_number,
            "credit_date": today.isoformat(),
            "credit_date_label": today.strftime("%d %b %Y"),
            "reference_number": "",
            "amount": "0.00",
            "currency": currency,
            "status": VendorCredit.Status.DRAFT,
            "action": "save_as_draft",
        },
        "fields": {
            "vendor_id": {
                "label": "Vendor",
                "required": True,
                "placeholder": "Select a vendor",
            },
            "credit_note_number": {"label": "Credit Note#", "required": True},
            "reference_number": {"label": "Reference#", "required": False},
            "credit_date": {"label": "Credit Date", "required": True},
            "amount": {"label": "Amount", "required": True},
        },
        "vendors": [vendor_option(row) for row in vendors],
        "counts": vendor_credit_counts(queryset),
        "actions": [
            {
                "key": "save_as_draft",
                "label": "Save as Draft",
                "path": "/api/vendor-credits/",
            },
            {
                "key": "save_as_open",
                "label": "Save as Open",
                "path": "/api/vendor-credits/",
            },
        ],
        "create_path": "/api/vendor-credits/",
        "export_path": "/api/vendor-credits/export/",
        "refresh_path": "/api/vendor-credits/refresh/",
    }


class VendorCreditView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor_credit_id = (
            request.query_params.get("vendor_credit_id")
            or request.query_params.get("credit_note_id")
            or request.query_params.get("id")
        )
        if vendor_credit_id:
            parsed_id, error_response = parse_uuid(vendor_credit_id, "vendor_credit_id")
            if error_response:
                return error_response
            vendor_credit = get_vendor_credit_queryset(request.user).filter(pk=parsed_id).first()
            if not vendor_credit:
                return api_error(
                    "Vendor credit not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return api_success(data=VendorCreditSerializer(vendor_credit).data)

        queryset, error_response = filtered_vendor_credit_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=VendorCreditSerializer)
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
                "Organization not found. Complete organization setup first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = VendorCreditWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            vendor_credit = serializer.save(
                organization=organization,
                created_by=request.user,
            )
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Credit note number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        vendor_credit = get_vendor_credit_queryset(request.user).get(pk=vendor_credit.pk)
        return api_success(
            data=VendorCreditSerializer(vendor_credit).data,
            message=success_message(vendor_credit),
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        vendor_credit_id, error_response = get_vendor_credit_id_param(request)
        if error_response:
            return error_response
        vendor_credit = get_vendor_credit_queryset(request.user).filter(
            pk=vendor_credit_id
        ).first()
        if not vendor_credit:
            return api_error(
                "Vendor credit not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = VendorCreditWriteSerializer(
            vendor_credit,
            data=request.data,
            partial=partial,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            vendor_credit = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Credit note number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        vendor_credit = get_vendor_credit_queryset(request.user).get(pk=vendor_credit.pk)
        return api_success(
            data=VendorCreditSerializer(vendor_credit).data,
            message="Vendor credit updated successfully.",
        )

    def delete(self, request):
        vendor_credit_id, error_response = get_vendor_credit_id_param(request)
        if error_response:
            return error_response
        vendor_credit = get_vendor_credit_queryset(request.user).filter(
            pk=vendor_credit_id
        ).first()
        if not vendor_credit:
            return api_error(
                "Vendor credit not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if vendor_credit.status in (VendorCredit.Status.OPEN, VendorCredit.Status.CLOSED):
            return api_error(
                "Open or closed vendor credits cannot be deleted. Void them instead.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        vendor_credit.delete()
        return api_success(message="Vendor credit deleted successfully.")


class VendorCreditOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_vendor_credit_queryset(request.user)
        return api_success(
            data={
                "tabs": [
                    {"key": key, "label": label} for key, label in VENDOR_CREDIT_TAB_FILTERS
                ],
                "statuses": [
                    {"key": key, "label": label}
                    for key, label in VENDOR_CREDIT_STATUS_FILTERS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "credit_note_number", "label": "Credit Note#"},
                    {"key": "vendor_name", "label": "Vendor Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/vendor-credits/form/",
                "counts": vendor_credit_counts(queryset),
                "actions": [
                    {
                        "key": "save_as_draft",
                        "label": "Save as Draft",
                        "path": "/api/vendor-credits/",
                    },
                    {
                        "key": "save_as_open",
                        "label": "Save as Open",
                        "path": "/api/vendor-credits/",
                    },
                    {
                        "key": "export",
                        "label": "Export Vendor Credits",
                        "description": "Export the current vendor credit list",
                        "path": "/api/vendor-credits/export/",
                    },
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "description": "Reload the latest vendor credits",
                        "path": "/api/vendor-credits/refresh/",
                    },
                    {
                        "key": "close",
                        "label": "Close",
                        "path": "/api/vendor-credits/close/",
                    },
                    {
                        "key": "void",
                        "label": "Void",
                        "path": "/api/vendor-credits/void/",
                    },
                ],
            }
        )


class VendorCreditFormView(APIView):
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
        data = build_vendor_credit_form(request.user, organization)
        vendor_credit_id = (
            request.query_params.get("vendor_credit_id")
            or request.query_params.get("credit_note_id")
            or request.query_params.get("id")
        )
        if vendor_credit_id:
            parsed_id, error_response = parse_uuid(vendor_credit_id, "vendor_credit_id")
            if error_response:
                return error_response
            vendor_credit = get_vendor_credit_queryset(request.user).filter(
                pk=parsed_id
            ).first()
            if not vendor_credit:
                return api_error(
                    "Vendor credit not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            data["title"] = "Edit Vendor Credit"
            data["vendor_credit"] = VendorCreditSerializer(vendor_credit).data
        return api_success(data=data)


class VendorCreditRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_vendor_credit_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=VendorCreditSerializer)
        if response is not None:
            response.data["message"] = "Vendor credits refreshed."
            return response
        return api_success(data=[], message="Vendor credits refreshed.")


class VendorCreditExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_vendor_credit_queryset(request)
        if error_response:
            return error_response
        rows = VendorCreditSerializer(queryset, many=True).data
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
                    "vendor_credit_id",
                    "credit_note_number",
                    "vendor_name",
                    "credit_date",
                    "status",
                    "amount",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "vendor_credit_id": row["vendor_credit_id"],
                        "credit_note_number": row["credit_note_number"],
                        "vendor_name": row["vendor_name"],
                        "credit_date": row["credit_date"],
                        "status": row["status"],
                        "amount": row["amount"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="vendor_credits.csv"'
            return response
        return api_success(
            data={"count": len(rows), "vendor_credits": rows},
            message="Vendor credits exported successfully.",
        )


class VendorCreditCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        vendor_credit_id, error_response = get_vendor_credit_id_param(request)
        if error_response:
            return error_response
        vendor_credit = get_vendor_credit_queryset(request.user).filter(
            pk=vendor_credit_id
        ).first()
        if not vendor_credit:
            return api_error(
                "Vendor credit not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if vendor_credit.status != VendorCredit.Status.OPEN:
            return api_error(
                "Only open vendor credits can be closed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        vendor_credit.status = VendorCredit.Status.CLOSED
        if not vendor_credit.closed_at:
            vendor_credit.closed_at = timezone.now()
        vendor_credit.save(update_fields=["status", "closed_at", "updated_at"])
        vendor_credit = get_vendor_credit_queryset(request.user).get(pk=vendor_credit.pk)
        return api_success(
            data=VendorCreditSerializer(vendor_credit).data,
            message="Vendor credit closed.",
        )


class VendorCreditVoidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        vendor_credit_id, error_response = get_vendor_credit_id_param(request)
        if error_response:
            return error_response
        vendor_credit = get_vendor_credit_queryset(request.user).filter(
            pk=vendor_credit_id
        ).first()
        if not vendor_credit:
            return api_error(
                "Vendor credit not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if vendor_credit.status in (VendorCredit.Status.CLOSED, VendorCredit.Status.VOID):
            return api_error(
                "This vendor credit cannot be voided.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        vendor_credit.status = VendorCredit.Status.VOID
        if not vendor_credit.voided_at:
            vendor_credit.voided_at = timezone.now()
        vendor_credit.save(update_fields=["status", "voided_at", "updated_at"])
        vendor_credit = get_vendor_credit_queryset(request.user).get(pk=vendor_credit.pk)
        return api_success(
            data=VendorCreditSerializer(vendor_credit).data,
            message="Vendor credit voided.",
        )
