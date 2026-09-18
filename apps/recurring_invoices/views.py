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
from apps.invoices.models import Invoice
from apps.invoices.serializers import InvoiceSerializer, InvoiceWriteSerializer
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.recurring_invoices.filters import (
    PROFILE_STATUS_FILTERS,
    PROFILE_TAB_FILTERS,
    RecurringInvoiceFilter,
    expired_q,
)
from apps.recurring_invoices.models import RecurringInvoice, RecurringInvoiceActivity
from apps.recurring_invoices.serializers import (
    RecurringInvoiceSerializer,
    RecurringInvoiceWriteSerializer,
    log_activity,
)

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "profile_name": "profile_name",
    "customer_name": "customer__display_name",
    "amount": "amount",
    "start_date": "start_date",
    "date": "start_date",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_profile_queryset(user):
    return RecurringInvoice.objects.filter(organization__owner=user).select_related(
        "organization",
        "customer",
        "created_by",
    ).prefetch_related("activities__created_by")


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


def get_profile_id_param(request):
    profile_id = (
        request.query_params.get("recurring_invoice_id")
        or request.query_params.get("profile_id")
        or request.query_params.get("id")
        or request.data.get("recurring_invoice_id")
        or request.data.get("profile_id")
        or request.data.get("id")
    )
    if not profile_id:
        return None, api_error(
            "recurring_invoice_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(profile_id, "recurring_invoice_id")


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


def filtered_profile_queryset(request):
    queryset = get_profile_queryset(request.user)
    profile_filter = RecurringInvoiceFilter(request.query_params, queryset=queryset)
    if not profile_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=profile_filter.errors)
    queryset, error_response = apply_sorting(profile_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def profile_counts(queryset):
    return {
        "all": queryset.count(),
        "active": queryset.filter(status=RecurringInvoice.Status.ACTIVE)
        .exclude(expired_q())
        .count(),
        "stopped": queryset.filter(status=RecurringInvoice.Status.STOPPED).count(),
        "expired": queryset.filter(expired_q()).count(),
        "draft": queryset.filter(status=RecurringInvoice.Status.DRAFT).count(),
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


def build_profile_form(user, organization):
    queryset = get_profile_queryset(user)
    customers = Customer.objects.filter(
        organization=organization,
        status=Customer.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    today = date.today()
    return {
        "title": "New Recurring Invoice",
        "defaults": {
            "frequency": RecurringInvoice.Frequency.MONTHLY,
            "start_date": today.isoformat(),
            "start_date_label": today.strftime("%d %b %Y"),
            "amount": "0.00",
            "currency": organization.currency if organization else "INR",
            "status": RecurringInvoice.Status.ACTIVE,
            "action": "save",
        },
        "fields": {
            "profile_name": {"label": "Profile Name", "required": True},
            "customer_id": {
                "label": "Customer Name",
                "required": True,
                "placeholder": "Start typing to select a Customer",
                "can_add": True,
                "add_path": "/api/customers/",
            },
            "frequency": {"label": "Frequency", "required": False},
            "start_date": {"label": "Start Date", "required": True},
            "amount": {"label": "Amount (₹)", "required": True},
        },
        "customers": [customer_option(row) for row in customers],
        "frequencies": [
            {"key": key, "label": label} for key, label in RecurringInvoice.Frequency.choices
        ],
        "counts": profile_counts(queryset),
        "actions": [
            {"key": "save", "label": "Save", "path": "/api/recurring-invoices/"},
            {
                "key": "save_as_draft",
                "label": "Save as Draft",
                "path": "/api/recurring-invoices/",
            },
        ],
        "create_path": "/api/recurring-invoices/",
        "detail_tabs": [
            {"key": "details", "label": "DETAILS"},
            {"key": "comments_and_history", "label": "COMMENTS & HISTORY"},
        ],
    }


class RecurringInvoiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile_id = (
            request.query_params.get("recurring_invoice_id")
            or request.query_params.get("id")
        )
        if profile_id:
            parsed_id, error_response = parse_uuid(profile_id, "recurring_invoice_id")
            if error_response:
                return error_response
            profile = get_profile_queryset(request.user).filter(pk=parsed_id).first()
            if not profile:
                return api_error(
                    "Recurring invoice not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return api_success(data=RecurringInvoiceSerializer(profile).data)

        queryset, error_response = filtered_profile_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(
            request,
            queryset,
            serializer=RecurringInvoiceSerializer,
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
                "Organization not found. Complete organization setup first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RecurringInvoiceWriteSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            profile = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Unable to create recurring invoice.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        profile = get_profile_queryset(request.user).get(pk=profile.pk)
        message = (
            "Recurring invoice saved as draft."
            if profile.status == RecurringInvoice.Status.DRAFT
            else "Recurring invoice saved."
        )
        return api_success(
            data=RecurringInvoiceSerializer(profile).data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        profile_id, error_response = get_profile_id_param(request)
        if error_response:
            return error_response
        profile = get_profile_queryset(request.user).filter(pk=profile_id).first()
        if not profile:
            return api_error(
                "Recurring invoice not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = RecurringInvoiceWriteSerializer(
            profile,
            data=request.data,
            partial=partial,
            context={"request": request},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            profile = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        profile = get_profile_queryset(request.user).get(pk=profile.pk)
        return api_success(
            data=RecurringInvoiceSerializer(profile).data,
            message="Recurring invoice updated successfully.",
        )

    def delete(self, request):
        profile_id, error_response = get_profile_id_param(request)
        if error_response:
            return error_response
        profile = get_profile_queryset(request.user).filter(pk=profile_id).first()
        if not profile:
            return api_error(
                "Recurring invoice not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        profile.delete()
        return api_success(message="Recurring invoice deleted successfully.")


class RecurringInvoiceOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_profile_queryset(request.user)
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in PROFILE_TAB_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in PROFILE_STATUS_FILTERS
                ],
                "frequencies": [
                    {"key": key, "label": label}
                    for key, label in RecurringInvoice.Frequency.choices
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "profile_name", "label": "Profile Name"},
                    {"key": "customer_name", "label": "Customer Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/recurring-invoices/form/",
                "counts": profile_counts(queryset),
                "detail_tabs": [
                    {"key": "details", "label": "DETAILS"},
                    {"key": "comments_and_history", "label": "COMMENTS & HISTORY"},
                ],
                "actions": [
                    {"key": "save", "label": "Save", "path": "/api/recurring-invoices/"},
                    {"key": "refresh", "label": "Refresh", "path": "/api/recurring-invoices/refresh/"},
                    {"key": "export", "label": "Export", "path": "/api/recurring-invoices/export/"},
                    {"key": "stop", "label": "Stop", "path": "/api/recurring-invoices/stop/"},
                    {"key": "resume", "label": "Resume", "path": "/api/recurring-invoices/resume/"},
                    {
                        "key": "generate",
                        "label": "Generate Invoice",
                        "path": "/api/recurring-invoices/generate/",
                    },
                ],
            }
        )


class RecurringInvoiceFormView(APIView):
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
        data = build_profile_form(request.user, organization)
        profile_id = (
            request.query_params.get("recurring_invoice_id")
            or request.query_params.get("id")
        )
        if profile_id:
            parsed_id, error_response = parse_uuid(profile_id, "recurring_invoice_id")
            if error_response:
                return error_response
            profile = get_profile_queryset(request.user).filter(pk=parsed_id).first()
            if not profile:
                return api_error(
                    "Recurring invoice not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            data["title"] = "Edit Recurring Invoice"
            data["recurring_invoice"] = RecurringInvoiceSerializer(profile).data
        return api_success(data=data)


class RecurringInvoiceRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_profile_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(
            request,
            queryset,
            serializer=RecurringInvoiceSerializer,
        )
        if response is not None:
            response.data["message"] = "Recurring invoices refreshed."
            return response
        return api_success(data=[], message="Recurring invoices refreshed.")


class RecurringInvoiceExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_profile_queryset(request)
        if error_response:
            return error_response
        rows = RecurringInvoiceSerializer(queryset, many=True).data
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
                    "recurring_invoice_id",
                    "profile_name",
                    "customer_name",
                    "frequency",
                    "start_date",
                    "amount",
                    "status",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "recurring_invoice_id": row["recurring_invoice_id"],
                        "profile_name": row["profile_name"],
                        "customer_name": row["customer_name"],
                        "frequency": row["frequency"],
                        "start_date": row["start_date"],
                        "amount": row["amount"],
                        "status": row["status"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="recurring_invoices.csv"'
            return response
        return api_success(
            data={"count": len(rows), "recurring_invoices": rows},
            message="Recurring invoices exported successfully.",
        )


class RecurringInvoiceStopView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile_id, error_response = get_profile_id_param(request)
        if error_response:
            return error_response
        profile = get_profile_queryset(request.user).filter(pk=profile_id).first()
        if not profile:
            return api_error(
                "Recurring invoice not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if profile.effective_status() == RecurringInvoice.Status.EXPIRED:
            return api_error(
                "Expired profiles cannot be stopped.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        profile.status = RecurringInvoice.Status.STOPPED
        profile.stopped_at = timezone.now()
        profile.save(update_fields=["status", "stopped_at", "updated_at"])
        log_activity(profile, "Profile stopped.", user=request.user)
        profile = get_profile_queryset(request.user).get(pk=profile.pk)
        return api_success(
            data=RecurringInvoiceSerializer(profile).data,
            message="Recurring invoice stopped.",
        )


class RecurringInvoiceResumeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile_id, error_response = get_profile_id_param(request)
        if error_response:
            return error_response
        profile = get_profile_queryset(request.user).filter(pk=profile_id).first()
        if not profile:
            return api_error(
                "Recurring invoice not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if profile.effective_status() == RecurringInvoice.Status.EXPIRED:
            return api_error(
                "Expired profiles cannot be resumed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        profile.status = RecurringInvoice.Status.ACTIVE
        profile.stopped_at = None
        if not profile.next_invoice_date:
            profile.next_invoice_date = date.today()
        profile.save(update_fields=["status", "stopped_at", "next_invoice_date", "updated_at"])
        log_activity(profile, "Profile resumed.", user=request.user)
        profile = get_profile_queryset(request.user).get(pk=profile.pk)
        return api_success(
            data=RecurringInvoiceSerializer(profile).data,
            message="Recurring invoice resumed.",
        )


class RecurringInvoiceCommentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile_id, error_response = get_profile_id_param(request)
        if error_response:
            return error_response
        profile = get_profile_queryset(request.user).filter(pk=profile_id).first()
        if not profile:
            return api_error(
                "Recurring invoice not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        message = (request.data.get("message") or request.data.get("comment") or "").strip()
        if not message:
            return api_error(
                "message is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        log_activity(
            profile,
            message,
            user=request.user,
            activity_type=RecurringInvoiceActivity.ActivityType.COMMENT,
        )
        profile = get_profile_queryset(request.user).get(pk=profile.pk)
        return api_success(
            data=RecurringInvoiceSerializer(profile).data,
            message="Comment added.",
            status_code=status.HTTP_201_CREATED,
        )


class RecurringInvoiceGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile_id, error_response = get_profile_id_param(request)
        if error_response:
            return error_response
        profile = get_profile_queryset(request.user).filter(pk=profile_id).first()
        if not profile:
            return api_error(
                "Recurring invoice not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if profile.effective_status() != RecurringInvoice.Status.ACTIVE:
            return api_error(
                "Only active profiles can generate invoices.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        payload = {
            "customer_id": str(profile.customer_id),
            "action": "save_as_draft",
            "subject": profile.profile_name,
            "invoice_date": date.today().isoformat(),
            "line_items": [
                {
                    "name": profile.profile_name,
                    "quantity": "1",
                    "rate": str(profile.amount),
                }
            ],
        }
        serializer = InvoiceWriteSerializer(data=payload)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            invoice = serializer.save(
                organization=profile.organization,
                created_by=request.user,
            )
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        today = date.today()
        profile.last_invoice_date = today
        profile.next_invoice_date = profile.next_date_after(today)
        if profile.end_date and profile.next_invoice_date > profile.end_date:
            profile.status = RecurringInvoice.Status.EXPIRED
        profile.save(
            update_fields=[
                "last_invoice_date",
                "next_invoice_date",
                "status",
                "updated_at",
            ]
        )
        log_activity(
            profile,
            f"Invoice {invoice.invoice_number} generated.",
            user=request.user,
        )
        invoice = Invoice.objects.select_related("customer", "organization").get(pk=invoice.pk)
        return api_success(
            data={
                "recurring_invoice": RecurringInvoiceSerializer(
                    get_profile_queryset(request.user).get(pk=profile.pk)
                ).data,
                "invoice": InvoiceSerializer(invoice).data,
            },
            message="Invoice generated from recurring profile.",
            status_code=status.HTTP_201_CREATED,
        )
