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
from apps.bills.filters import (
    BILL_STATUS_FILTERS,
    BILL_TAB_FILTERS,
    BillFilter,
    overdue_q,
)
from apps.bills.models import Bill
from apps.bills.serializers import (
    BillSerializer,
    BillWriteSerializer,
    default_due_date,
    next_bill_number,
)
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.vendors.models import Vendor

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "bill_date",
    "bill_date": "bill_date",
    "bill_number": "bill_number",
    "bill#": "bill_number",
    "vendor_name": "vendor__display_name",
    "amount": "amount",
    "due_date": "due_date",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_bill_queryset(user):
    return Bill.objects.filter(organization__owner=user).select_related(
        "organization",
        "vendor",
        "purchase_order",
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


def get_bill_id_param(request):
    bill_id = (
        request.query_params.get("bill_id")
        or request.query_params.get("id")
        or request.data.get("bill_id")
        or request.data.get("id")
    )
    if not bill_id:
        return None, api_error(
            "bill_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(bill_id, "bill_id")


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


def filtered_bill_queryset(request):
    queryset = get_bill_queryset(request.user)
    bill_filter = BillFilter(request.query_params, queryset=queryset)
    if not bill_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=bill_filter.errors)
    queryset, error_response = apply_sorting(bill_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def bill_counts(queryset):
    return {
        "all": queryset.count(),
        "draft": queryset.filter(status=Bill.Status.DRAFT).count(),
        "open": queryset.filter(status=Bill.Status.OPEN).exclude(overdue_q()).count(),
        "overdue": queryset.filter(overdue_q()).count(),
        "paid": queryset.filter(status=Bill.Status.PAID).count(),
        "partially_paid": queryset.filter(status=Bill.Status.PARTIALLY_PAID).count(),
    }


def vendor_option(vendor):
    name = vendor.display_name or vendor.company_name or ""
    return {
        "vendor_id": vendor.id,
        "display_name": name,
        "company_name": vendor.company_name or "",
        "initials": (name[:1] or "").upper(),
    }


def success_message(bill):
    if bill.status == Bill.Status.OPEN:
        if bill.is_overdue():
            return "Bill saved as open."
        return "Bill saved as open."
    if bill.status == Bill.Status.PAID:
        return "Bill marked as paid."
    if bill.status == Bill.Status.PARTIALLY_PAID:
        return "Bill marked as partially paid."
    return "Bill saved as draft."


def build_bill_form(user, organization):
    queryset = get_bill_queryset(user)
    vendors = Vendor.objects.filter(
        organization=organization,
        status=Vendor.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    today = date.today()
    due = default_due_date(today)
    next_number = next_bill_number(organization)
    currency = (organization.currency if organization else "INR") or "INR"
    return {
        "title": "New Bill",
        "next_bill_number": next_number,
        "defaults": {
            "bill_number": next_number,
            "bill_date": today.isoformat(),
            "bill_date_label": today.strftime("%d %b %Y"),
            "due_date": due.isoformat(),
            "due_date_label": due.strftime("%d %b %Y"),
            "amount": "0.00",
            "currency": currency,
            "status": Bill.Status.DRAFT,
            "action": "save_as_draft",
        },
        "fields": {
            "vendor_id": {
                "label": "Vendor",
                "required": True,
                "placeholder": "Select a vendor",
            },
            "bill_number": {"label": "Bill#", "required": True},
            "bill_date": {"label": "Bill Date", "required": True},
            "due_date": {"label": "Due Date", "required": True},
            "amount": {"label": "Amount", "required": True},
        },
        "vendors": [vendor_option(row) for row in vendors],
        "counts": bill_counts(queryset),
        "actions": [
            {"key": "save_as_draft", "label": "Save as Draft", "path": "/api/bills/"},
            {"key": "save_as_open", "label": "Save as Open", "path": "/api/bills/"},
        ],
        "create_path": "/api/bills/",
        "export_path": "/api/bills/export/",
        "refresh_path": "/api/bills/refresh/",
    }


class BillView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bill_id = request.query_params.get("bill_id") or request.query_params.get("id")
        if bill_id:
            parsed_id, error_response = parse_uuid(bill_id, "bill_id")
            if error_response:
                return error_response
            bill = get_bill_queryset(request.user).filter(pk=parsed_id).first()
            if not bill:
                return api_error("Bill not found.", status_code=status.HTTP_404_NOT_FOUND)
            return api_success(data=BillSerializer(bill).data)

        queryset, error_response = filtered_bill_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=BillSerializer)
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
                "Organization not found. Complete organization setup before creating bills.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = BillWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            bill = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Bill number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bill = get_bill_queryset(request.user).get(pk=bill.pk)
        return api_success(
            data=BillSerializer(bill).data,
            message=success_message(bill),
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        bill_id, error_response = get_bill_id_param(request)
        if error_response:
            return error_response
        bill = get_bill_queryset(request.user).filter(pk=bill_id).first()
        if not bill:
            return api_error("Bill not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = BillWriteSerializer(bill, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            bill = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Bill number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bill = get_bill_queryset(request.user).get(pk=bill.pk)
        return api_success(
            data=BillSerializer(bill).data,
            message="Bill updated successfully.",
        )

    def delete(self, request):
        bill_id, error_response = get_bill_id_param(request)
        if error_response:
            return error_response
        bill = get_bill_queryset(request.user).filter(pk=bill_id).first()
        if not bill:
            return api_error("Bill not found.", status_code=status.HTTP_404_NOT_FOUND)
        if bill.status != Bill.Status.DRAFT:
            return api_error(
                "Only draft bills can be deleted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bill.delete()
        return api_success(message="Bill deleted successfully.")


class BillOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_bill_queryset(request.user)
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in BILL_TAB_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in BILL_STATUS_FILTERS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "bill_number", "label": "Bill#"},
                    {"key": "vendor_name", "label": "Vendor Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/bills/form/",
                "counts": bill_counts(queryset),
                "actions": [
                    {"key": "save_as_draft", "label": "Save as Draft", "path": "/api/bills/"},
                    {"key": "save_as_open", "label": "Save as Open", "path": "/api/bills/"},
                    {"key": "export", "label": "Export Bills", "path": "/api/bills/export/"},
                    {"key": "refresh", "label": "Refresh", "path": "/api/bills/refresh/"},
                    {"key": "mark_as_paid", "label": "Mark as Paid", "path": "/api/bills/mark-paid/"},
                    {
                        "key": "mark_as_partially_paid",
                        "label": "Mark as Partially Paid",
                        "path": "/api/bills/mark-partially-paid/",
                    },
                ],
            }
        )


class BillFormView(APIView):
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
        data = build_bill_form(request.user, organization)
        bill_id = request.query_params.get("bill_id") or request.query_params.get("id")
        if bill_id:
            parsed_id, error_response = parse_uuid(bill_id, "bill_id")
            if error_response:
                return error_response
            bill = get_bill_queryset(request.user).filter(pk=parsed_id).first()
            if not bill:
                return api_error("Bill not found.", status_code=status.HTTP_404_NOT_FOUND)
            data["title"] = "Edit Bill"
            data["bill"] = BillSerializer(bill).data
        return api_success(data=data)


class BillRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_bill_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=BillSerializer)
        if response is not None:
            response.data["message"] = "Bills refreshed."
            return response
        return api_success(data=[], message="Bills refreshed.")


class BillExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_bill_queryset(request)
        if error_response:
            return error_response
        rows = BillSerializer(queryset, many=True).data
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
                    "bill_id",
                    "bill_number",
                    "vendor_name",
                    "bill_date",
                    "due_date",
                    "status",
                    "amount",
                    "amount_paid",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "bill_id": row["bill_id"],
                        "bill_number": row["bill_number"],
                        "vendor_name": row["vendor_name"],
                        "bill_date": row["bill_date"],
                        "due_date": row["due_date"],
                        "status": row["status"],
                        "amount": row["amount"],
                        "amount_paid": row["amount_paid"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="bills.csv"'
            return response
        return api_success(
            data={"count": len(rows), "bills": rows},
            message="Bills exported successfully.",
        )


class BillMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        bill_id, error_response = get_bill_id_param(request)
        if error_response:
            return error_response
        bill = get_bill_queryset(request.user).filter(pk=bill_id).first()
        if not bill:
            return api_error("Bill not found.", status_code=status.HTTP_404_NOT_FOUND)
        if bill.status not in (Bill.Status.OPEN, Bill.Status.PARTIALLY_PAID):
            return api_error(
                "Only open or partially paid bills can be marked as paid.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bill.status = Bill.Status.PAID
        bill.amount_paid = bill.amount
        if not bill.paid_at:
            bill.paid_at = timezone.now()
        bill.save(update_fields=["status", "amount_paid", "paid_at", "updated_at"])
        bill = get_bill_queryset(request.user).get(pk=bill.pk)
        return api_success(
            data=BillSerializer(bill).data,
            message="Bill marked as paid.",
        )


class BillMarkPartiallyPaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        bill_id, error_response = get_bill_id_param(request)
        if error_response:
            return error_response
        bill = get_bill_queryset(request.user).filter(pk=bill_id).first()
        if not bill:
            return api_error("Bill not found.", status_code=status.HTTP_404_NOT_FOUND)
        if bill.status != Bill.Status.OPEN:
            return api_error(
                "Only open bills can be marked as partially paid.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        amount_paid = request.data.get("amount_paid")
        if amount_paid is None:
            return api_error(
                "amount_paid is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bill.status = Bill.Status.PARTIALLY_PAID
        bill.amount_paid = amount_paid
        bill.save(update_fields=["status", "amount_paid", "updated_at"])
        bill = get_bill_queryset(request.user).get(pk=bill.pk)
        return api_success(
            data=BillSerializer(bill).data,
            message="Bill marked as partially paid.",
        )
