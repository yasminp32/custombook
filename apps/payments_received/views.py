from datetime import date
from uuid import UUID

from django.db import IntegrityError
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as SerializerValidationError
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.payments_received.filters import (
    PAYMENT_MODE_FILTERS,
    PAYMENT_STATUS_FILTERS,
    PAYMENT_TAB_FILTERS,
    PaymentReceivedFilter,
)
from apps.payments_received.models import PaymentReceived
from apps.payments_received.serializers import (
    PaymentReceivedSerializer,
    PaymentReceivedWriteSerializer,
    apply_amount_to_invoice,
    invoice_balance,
    next_payment_number,
    reverse_application,
)

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "payment_date",
    "payment_date": "payment_date",
    "payment_number": "payment_number",
    "payment#": "payment_number",
    "customer_name": "customer__display_name",
    "amount": "amount",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_payment_queryset(user):
    return PaymentReceived.objects.filter(organization__owner=user).select_related(
        "organization",
        "customer",
        "created_by",
    ).prefetch_related("applications__invoice")


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
    payment_filter = PaymentReceivedFilter(request.query_params, queryset=queryset)
    if not payment_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=payment_filter.errors)
    queryset, error_response = apply_sorting(payment_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def customer_option(customer):
    return {
        "customer_id": customer.id,
        "display_name": customer.display_name or customer.company_name or customer.name,
        "company_name": customer.company_name or "",
        "currency": customer.currency or "INR",
        "email": customer.email or "",
        "customer_details_path": f"/api/customers/?customer_id={customer.id}",
    }


def unpaid_invoices(organization, customer_id=None):
    queryset = Invoice.objects.filter(
        organization=organization,
    ).exclude(status=Invoice.Status.CANCELLED).exclude(status=Invoice.Status.PAID)
    if customer_id:
        queryset = queryset.filter(customer_id=customer_id)
    rows = []
    for invoice in queryset.select_related("customer").order_by("-invoice_date")[:100]:
        balance = invoice_balance(invoice)
        if balance <= 0:
            continue
        rows.append(
            {
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_id": invoice.customer_id,
                "customer_name": (
                    (
                        invoice.customer.display_name
                        or invoice.customer.company_name
                        or invoice.customer.name
                    )
                    if invoice.customer
                    else ""
                ),
                "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                "total_amount": f"{invoice.total_amount:.2f}",
                "amount_paid": f"{invoice.amount_paid:.2f}",
                "balance_due": f"{balance:.2f}",
                "currency": invoice.currency or "INR",
            }
        )
    return rows


def build_payment_form(user, organization, customer_id=None):
    queryset = get_payment_queryset(user)
    customers = Customer.objects.filter(
        organization=organization,
        status=Customer.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    today = date.today()
    next_number = next_payment_number(organization)
    return {
        "title": "New Payment",
        "next_payment_number": next_number,
        "defaults": {
            "payment_number": next_number,
            "payment_date": today.isoformat(),
            "payment_date_label": today.strftime("%d %b %Y"),
            "payment_mode": PaymentReceived.PaymentMode.BANK_TRANSFER,
            "reference_number": "",
            "amount": "0.00",
            "currency": organization.currency if organization else "INR",
            "action": "save",
        },
        "fields": {
            "customer_id": {
                "label": "Customer Name",
                "required": True,
                "placeholder": "Start typing to select a Customer",
                "can_add": True,
                "add_path": "/api/customers/",
            },
            "payment_number": {"label": "Payment#", "required": True},
            "payment_date": {"label": "Payment Date", "required": True},
            "payment_mode": {"label": "Payment Mode", "required": False},
            "reference_number": {"label": "Reference#", "required": False},
            "amount": {"label": "Amount (₹)", "required": True},
        },
        "customers": [customer_option(row) for row in customers],
        "payment_modes": [
            {"key": key, "label": label} for key, label in PaymentReceived.PaymentMode.choices
        ],
        "unpaid_invoices": unpaid_invoices(organization, customer_id),
        "counts": {
            "all": queryset.count(),
            "this_month": queryset.filter(
                payment_date__year=today.year,
                payment_date__month=today.month,
            ).count(),
            "unapplied": queryset.filter(amount_applied__lt=F("amount")).count(),
        },
        "actions": [
            {"key": "save", "label": "Save", "path": "/api/payments-received/"},
        ],
        "create_path": "/api/payments-received/",
    }


class PaymentReceivedView(APIView):
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
            return api_success(data=PaymentReceivedSerializer(payment).data)

        queryset, error_response = filtered_payment_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=PaymentReceivedSerializer)
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
        serializer = PaymentReceivedWriteSerializer(data=request.data)
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
        message = (
            "Payment recorded and applied."
            if not payment.is_unapplied()
            else "Payment recorded."
        )
        return api_success(
            data=PaymentReceivedSerializer(payment).data,
            message=message,
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
        serializer = PaymentReceivedWriteSerializer(payment, data=request.data, partial=partial)
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
            data=PaymentReceivedSerializer(payment).data,
            message="Payment updated successfully.",
        )

    def delete(self, request):
        payment_id, error_response = get_payment_id_param(request)
        if error_response:
            return error_response
        payment = get_payment_queryset(request.user).filter(pk=payment_id).first()
        if not payment:
            return api_error("Payment not found.", status_code=status.HTTP_404_NOT_FOUND)
        for application in list(payment.applications.select_related("invoice", "payment")):
            reverse_application(application)
        payment.delete()
        return api_success(message="Payment deleted successfully.")


class PaymentReceivedOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_payment_queryset(request.user)
        today = date.today()
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in PAYMENT_TAB_FILTERS],
                "modes": [{"key": key, "label": label} for key, label in PAYMENT_MODE_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in PAYMENT_STATUS_FILTERS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "payment_number", "label": "Payment#"},
                    {"key": "customer_name", "label": "Customer Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/payments-received/form/",
                "counts": {
                    "all": queryset.count(),
                    "this_month": queryset.filter(
                        payment_date__year=today.year,
                        payment_date__month=today.month,
                    ).count(),
                    "unapplied": queryset.filter(amount_applied__lt=F("amount")).count(),
                    "applied": queryset.filter(amount_applied__gte=F("amount")).count(),
                },
                "actions": [
                    {"key": "save", "label": "Save", "path": "/api/payments-received/"},
                    {"key": "refresh", "label": "Refresh", "path": "/api/payments-received/refresh/"},
                    {"key": "export", "label": "Export Payments", "path": "/api/payments-received/export/"},
                    {"key": "apply", "label": "Apply to Invoice", "path": "/api/payments-received/apply/"},
                    {"key": "unapply", "label": "Unapply", "path": "/api/payments-received/unapply/"},
                ],
            }
        )


class PaymentReceivedFormView(APIView):
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
        customer_id = request.query_params.get("customer_id")
        data = build_payment_form(request.user, organization, customer_id)
        payment_id = request.query_params.get("payment_id") or request.query_params.get("id")
        if payment_id:
            parsed_id, error_response = parse_uuid(payment_id, "payment_id")
            if error_response:
                return error_response
            payment = get_payment_queryset(request.user).filter(pk=parsed_id).first()
            if not payment:
                return api_error("Payment not found.", status_code=status.HTTP_404_NOT_FOUND)
            data["title"] = "Edit Payment"
            data["payment"] = PaymentReceivedSerializer(payment).data
        return api_success(data=data)


class PaymentReceivedRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_payment_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=PaymentReceivedSerializer)
        if response is not None:
            response.data["message"] = "Payments refreshed."
            return response
        return api_success(data=[], message="Payments refreshed.")


class PaymentReceivedExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_payment_queryset(request)
        if error_response:
            return error_response
        rows = PaymentReceivedSerializer(queryset, many=True).data
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
                    "customer_name",
                    "payment_date",
                    "payment_mode",
                    "amount",
                    "unused_amount",
                    "status",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "payment_id": row["payment_id"],
                        "payment_number": row["payment_number"],
                        "customer_name": row["customer_name"],
                        "payment_date": row["payment_date"],
                        "payment_mode": row["payment_mode"],
                        "amount": row["amount"],
                        "unused_amount": row["unused_amount"],
                        "status": row["status"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="payments_received.csv"'
            return response
        return api_success(
            data={"count": len(rows), "payments": rows},
            message="Payments exported successfully.",
        )


class PaymentReceivedApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id, error_response = get_payment_id_param(request)
        if error_response:
            return error_response
        payment = get_payment_queryset(request.user).filter(pk=payment_id).first()
        if not payment:
            return api_error("Payment not found.", status_code=status.HTTP_404_NOT_FOUND)
        invoice_id = request.data.get("invoice_id") or request.query_params.get("invoice_id")
        parsed_invoice_id, error_response = parse_uuid(invoice_id, "invoice_id")
        if error_response:
            return error_response
        invoice = Invoice.objects.filter(
            pk=parsed_invoice_id,
            organization=payment.organization,
        ).first()
        if not invoice:
            return api_error("Invoice not found.", status_code=status.HTTP_404_NOT_FOUND)
        amount = request.data.get("amount")
        if amount is None:
            amount = min(payment.unused_amount, invoice_balance(invoice))
        try:
            apply_amount_to_invoice(payment, invoice, amount)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        payment = get_payment_queryset(request.user).get(pk=payment.pk)
        return api_success(
            data=PaymentReceivedSerializer(payment).data,
            message="Payment applied to invoice.",
        )


class PaymentReceivedUnapplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id, error_response = get_payment_id_param(request)
        if error_response:
            return error_response
        payment = get_payment_queryset(request.user).filter(pk=payment_id).first()
        if not payment:
            return api_error("Payment not found.", status_code=status.HTTP_404_NOT_FOUND)
        application_id = request.data.get("application_id") or request.query_params.get(
            "application_id"
        )
        invoice_id = request.data.get("invoice_id") or request.query_params.get("invoice_id")
        if application_id:
            parsed_id, error_response = parse_uuid(application_id, "application_id")
            if error_response:
                return error_response
            application = payment.applications.filter(pk=parsed_id).first()
        elif invoice_id:
            parsed_id, error_response = parse_uuid(invoice_id, "invoice_id")
            if error_response:
                return error_response
            application = payment.applications.filter(invoice_id=parsed_id).first()
        else:
            application = payment.applications.order_by("-created_at").first()
        if not application:
            return api_error(
                "No application found to unapply.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        reverse_application(application)
        payment = get_payment_queryset(request.user).get(pk=payment.pk)
        return api_success(
            data=PaymentReceivedSerializer(payment).data,
            message="Payment unapplied successfully.",
        )
