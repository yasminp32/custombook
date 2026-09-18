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
from apps.credit_notes.filters import (
    CREDIT_NOTE_STATUS_FILTERS,
    CREDIT_NOTE_TAB_FILTERS,
    CreditNoteFilter,
)
from apps.credit_notes.models import CreditNote
from apps.credit_notes.serializers import (
    CreditNoteSerializer,
    CreditNoteWriteSerializer,
    next_credit_note_number,
)
from apps.customers.models import Customer
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "credit_note_date",
    "credit_note_date": "credit_note_date",
    "credit_note_number": "credit_note_number",
    "credit_note#": "credit_note_number",
    "customer_name": "customer__display_name",
    "amount": "amount",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_credit_note_queryset(user):
    return CreditNote.objects.filter(organization__owner=user).select_related(
        "organization",
        "customer",
        "invoice",
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


def get_credit_note_id_param(request):
    credit_note_id = (
        request.query_params.get("credit_note_id")
        or request.query_params.get("id")
        or request.data.get("credit_note_id")
        or request.data.get("id")
    )
    if not credit_note_id:
        return None, api_error(
            "credit_note_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(credit_note_id, "credit_note_id")


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


def filtered_credit_note_queryset(request):
    queryset = get_credit_note_queryset(request.user)
    credit_note_filter = CreditNoteFilter(request.query_params, queryset=queryset)
    if not credit_note_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=credit_note_filter.errors)
    queryset, error_response = apply_sorting(credit_note_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def credit_note_counts(queryset):
    return {
        "all": queryset.count(),
        "open": queryset.filter(status=CreditNote.Status.OPEN).count(),
        "closed": queryset.filter(status=CreditNote.Status.CLOSED).count(),
        "draft": queryset.filter(status=CreditNote.Status.DRAFT).count(),
        "void": queryset.filter(status=CreditNote.Status.VOID).count(),
    }


def customer_option(customer):
    name = customer.display_name or customer.company_name or customer.name
    return {
        "customer_id": customer.id,
        "display_name": name,
        "company_name": customer.company_name or "",
        "initials": (name[:1] or "").upper(),
        "currency": customer.currency or "INR",
        "customer_details_path": f"/api/customers/?customer_id={customer.id}",
    }


def success_message(credit_note):
    if credit_note.status == CreditNote.Status.OPEN:
        return "Credit note saved as open."
    if credit_note.status == CreditNote.Status.CLOSED:
        return "Credit note closed."
    if credit_note.status == CreditNote.Status.VOID:
        return "Credit note voided."
    return "Credit note saved as draft."


def build_credit_note_form(user, organization):
    queryset = get_credit_note_queryset(user)
    customers = Customer.objects.filter(
        organization=organization,
        status=Customer.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    today = date.today()
    next_number = next_credit_note_number(organization)
    return {
        "title": "New Credit Note",
        "next_credit_note_number": next_number,
        "defaults": {
            "credit_note_number": next_number,
            "credit_note_date": today.isoformat(),
            "credit_note_date_label": today.strftime("%d %b %Y"),
            "reference_number": "",
            "amount": "0.00",
            "currency": organization.currency if organization else "INR",
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
            "credit_note_number": {"label": "Credit Note#", "required": True},
            "reference_number": {"label": "Reference#", "required": False},
            "credit_note_date": {"label": "Credit Note Date", "required": True},
            "amount": {"label": "Amount (₹)", "required": True},
        },
        "customers": [customer_option(row) for row in customers],
        "counts": credit_note_counts(queryset),
        "actions": [
            {
                "key": "save_as_draft",
                "label": "Save as Draft",
                "path": "/api/credit-notes/",
            },
            {
                "key": "save_as_open",
                "label": "Save as Open",
                "path": "/api/credit-notes/",
            },
        ],
        "create_path": "/api/credit-notes/",
    }


class CreditNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        credit_note_id = (
            request.query_params.get("credit_note_id")
            or request.query_params.get("id")
        )
        if credit_note_id:
            parsed_id, error_response = parse_uuid(credit_note_id, "credit_note_id")
            if error_response:
                return error_response
            credit_note = get_credit_note_queryset(request.user).filter(pk=parsed_id).first()
            if not credit_note:
                return api_error("Credit note not found.", status_code=status.HTTP_404_NOT_FOUND)
            return api_success(data=CreditNoteSerializer(credit_note).data)

        queryset, error_response = filtered_credit_note_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=CreditNoteSerializer)
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
        serializer = CreditNoteWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            credit_note = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Credit note number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        credit_note = get_credit_note_queryset(request.user).get(pk=credit_note.pk)
        return api_success(
            data=CreditNoteSerializer(credit_note).data,
            message=success_message(credit_note),
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        credit_note_id, error_response = get_credit_note_id_param(request)
        if error_response:
            return error_response
        credit_note = get_credit_note_queryset(request.user).filter(pk=credit_note_id).first()
        if not credit_note:
            return api_error("Credit note not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = CreditNoteWriteSerializer(credit_note, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            credit_note = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Credit note number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        credit_note = get_credit_note_queryset(request.user).get(pk=credit_note.pk)
        return api_success(
            data=CreditNoteSerializer(credit_note).data,
            message="Credit note updated successfully.",
        )

    def delete(self, request):
        credit_note_id, error_response = get_credit_note_id_param(request)
        if error_response:
            return error_response
        credit_note = get_credit_note_queryset(request.user).filter(pk=credit_note_id).first()
        if not credit_note:
            return api_error("Credit note not found.", status_code=status.HTTP_404_NOT_FOUND)
        if credit_note.status in (CreditNote.Status.OPEN, CreditNote.Status.CLOSED):
            return api_error(
                "Open or closed credit notes cannot be deleted. Void them instead.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        credit_note.delete()
        return api_success(message="Credit note deleted successfully.")


class CreditNoteOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_credit_note_queryset(request.user)
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in CREDIT_NOTE_TAB_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in CREDIT_NOTE_STATUS_FILTERS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "credit_note_number", "label": "Credit Note#"},
                    {"key": "customer_name", "label": "Customer Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/credit-notes/form/",
                "counts": credit_note_counts(queryset),
                "actions": [
                    {"key": "save_as_draft", "label": "Save as Draft", "path": "/api/credit-notes/"},
                    {"key": "save_as_open", "label": "Save as Open", "path": "/api/credit-notes/"},
                    {"key": "refresh", "label": "Refresh", "path": "/api/credit-notes/refresh/"},
                    {"key": "export", "label": "Export Credit Notes", "path": "/api/credit-notes/export/"},
                    {"key": "close", "label": "Close", "path": "/api/credit-notes/close/"},
                    {"key": "void", "label": "Void", "path": "/api/credit-notes/void/"},
                ],
            }
        )


class CreditNoteFormView(APIView):
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
        data = build_credit_note_form(request.user, organization)
        credit_note_id = (
            request.query_params.get("credit_note_id")
            or request.query_params.get("id")
        )
        if credit_note_id:
            parsed_id, error_response = parse_uuid(credit_note_id, "credit_note_id")
            if error_response:
                return error_response
            credit_note = get_credit_note_queryset(request.user).filter(pk=parsed_id).first()
            if not credit_note:
                return api_error("Credit note not found.", status_code=status.HTTP_404_NOT_FOUND)
            data["title"] = "Edit Credit Note"
            data["credit_note"] = CreditNoteSerializer(credit_note).data
        return api_success(data=data)


class CreditNoteRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_credit_note_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=CreditNoteSerializer)
        if response is not None:
            response.data["message"] = "Credit notes refreshed."
            return response
        return api_success(data=[], message="Credit notes refreshed.")


class CreditNoteExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_credit_note_queryset(request)
        if error_response:
            return error_response
        rows = CreditNoteSerializer(queryset, many=True).data
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
                    "credit_note_id",
                    "credit_note_number",
                    "customer_name",
                    "credit_note_date",
                    "status",
                    "amount",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "credit_note_id": row["credit_note_id"],
                        "credit_note_number": row["credit_note_number"],
                        "customer_name": row["customer_name"],
                        "credit_note_date": row["credit_note_date"],
                        "status": row["status"],
                        "amount": row["amount"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="credit_notes.csv"'
            return response
        return api_success(
            data={"count": len(rows), "credit_notes": rows},
            message="Credit notes exported successfully.",
        )


class CreditNoteCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        credit_note_id, error_response = get_credit_note_id_param(request)
        if error_response:
            return error_response
        credit_note = get_credit_note_queryset(request.user).filter(pk=credit_note_id).first()
        if not credit_note:
            return api_error("Credit note not found.", status_code=status.HTTP_404_NOT_FOUND)
        if credit_note.status != CreditNote.Status.OPEN:
            return api_error(
                "Only open credit notes can be closed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        credit_note.status = CreditNote.Status.CLOSED
        if not credit_note.closed_at:
            credit_note.closed_at = timezone.now()
        credit_note.save(update_fields=["status", "closed_at", "updated_at"])
        credit_note = get_credit_note_queryset(request.user).get(pk=credit_note.pk)
        return api_success(
            data=CreditNoteSerializer(credit_note).data,
            message="Credit note closed.",
        )


class CreditNoteVoidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        credit_note_id, error_response = get_credit_note_id_param(request)
        if error_response:
            return error_response
        credit_note = get_credit_note_queryset(request.user).filter(pk=credit_note_id).first()
        if not credit_note:
            return api_error("Credit note not found.", status_code=status.HTTP_404_NOT_FOUND)
        if credit_note.status in (CreditNote.Status.CLOSED, CreditNote.Status.VOID):
            return api_error(
                "This credit note cannot be voided.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        credit_note.status = CreditNote.Status.VOID
        if not credit_note.voided_at:
            credit_note.voided_at = timezone.now()
        credit_note.save(update_fields=["status", "voided_at", "updated_at"])
        credit_note = get_credit_note_queryset(request.user).get(pk=credit_note.pk)
        return api_success(
            data=CreditNoteSerializer(credit_note).data,
            message="Credit note voided.",
        )
