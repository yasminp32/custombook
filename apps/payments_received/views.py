import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as SerializerValidationError
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.accounts.throttles import PaymentReceiptEmailThrottle, ThrottledResponseMixin
from apps.attachments.models import Attachment
from apps.banking.models import BankAccount
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.payments_received.emails import build_email_form, parse_recipients, send_receipt_email
from apps.payments_received.filters import (
    PAYMENT_MODE_FILTERS,
    PAYMENT_STATUS_FILTERS,
    PAYMENT_TAB_FILTERS,
    PaymentReceivedFilter,
)
from apps.payments_received.models import PaymentReceived
from apps.payments_received.pdf import build_receipt_pdf, receipt_filename
from apps.payments_received.serializers import (
    PaymentReceivedActivitySerializer,
    PaymentReceivedSerializer,
    PaymentReceivedWriteSerializer,
    apply_amount_to_invoice,
    invoice_balance,
    money,
    next_payment_number,
    reverse_application,
)
from apps.payments_received.services import (
    ATTACHABLE_TYPE,
    applications_snapshot,
    currency_amount,
    edit_snapshot,
    log_activity,
    template_options,
)

logger = logging.getLogger(__name__)

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
        PaymentReceived.objects.filter(organization__owner=user)
        .select_related("organization", "customer", "created_by")
        .prefetch_related("applications__invoice")
        .annotate(
            attachments_total=Coalesce(
                Subquery(attachments_total, output_field=IntegerField()),
                0,
            )
        )
    )


def get_payment_from_request(request):
    payment_id, error_response = get_payment_id_param(request)
    if error_response:
        return None, error_response
    payment = get_payment_queryset(request.user).filter(pk=payment_id).first()
    if not payment:
        return None, api_error("Payment not found.", status_code=status.HTTP_404_NOT_FOUND)
    return payment, None


def void_error(payment, action="edited"):
    if not payment.is_void:
        return None
    return api_error(
        f"Voided payments cannot be {action}.",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


def refetch(request, payment):
    return get_payment_queryset(request.user).get(pk=payment.pk)


def log_update(payment, user, before, before_applications):
    after_applications = applications_snapshot(payment)
    if edit_snapshot(payment) != before:
        log_activity(payment, "Payment details modified.", user=user)
    if after_applications != before_applications:
        log_activity(payment, "Invoice payment details modified.", user=user)


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


def payment_invoices(payment):
    applied = {row.invoice_id: Decimal(row.amount or 0) for row in payment.applications.all()}
    queryset = (
        Invoice.objects.filter(organization=payment.organization, customer_id=payment.customer_id)
        .exclude(status=Invoice.Status.CANCELLED)
        .filter(Q(id__in=applied.keys()) | ~Q(status=Invoice.Status.PAID))
        .order_by("invoice_date", "created_at")
    )
    rows = []
    for invoice in queryset[:200]:
        payment_amount = applied.get(invoice.id, Decimal("0"))
        due = invoice_balance(invoice) + payment_amount
        if due <= 0 and not payment_amount:
            continue
        rows.append(
            {
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                "invoice_date_label": (
                    invoice.invoice_date.strftime("%d %b %Y") if invoice.invoice_date else ""
                ),
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "invoice_amount": money(invoice.total_amount),
                "amount_due": money(due),
                "payment_amount": money(payment_amount),
                "currency": invoice.currency or payment.currency or "INR",
            }
        )
    return rows


def bank_account_options(organization):
    return [
        {
            "bank_account_id": account.id,
            "name": account.name,
            "account_type": account.account_type,
            "bank_name": account.bank_name,
            "currency": account.currency,
        }
        for account in BankAccount.objects.filter(organization=organization).order_by("name")[:200]
    ]


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
            "bank_charges": {"label": "Bank Charges (if any)", "required": False},
            "bank_account_id": {"label": "Deposit To", "required": False},
        },
        "customers": [customer_option(row) for row in customers],
        "payment_modes": [
            {"key": key, "label": label} for key, label in PaymentReceived.PaymentMode.choices
        ],
        "bank_accounts": bank_account_options(organization),
        "unpaid_invoices": unpaid_invoices(organization, customer_id),
        "counts": {
            "all": queryset.count(),
            "this_month": queryset.filter(
                payment_date__year=today.year,
                payment_date__month=today.month,
            ).count(),
            "unapplied": queryset.filter(
                amount_applied__lt=F("amount"),
                voided_at__isnull=True,
            ).count(),
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
        log_activity(
            payment,
            f"Payment of {currency_amount(payment.currency, payment.amount)} received.",
            user=request.user,
        )
        for application in payment.applications.select_related("invoice"):
            log_activity(
                payment,
                f"Payment of {currency_amount(payment.currency, application.amount)} "
                f"applied to {application.invoice.invoice_number}.",
                user=request.user,
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
        error_response = void_error(payment)
        if error_response:
            return error_response
        serializer = PaymentReceivedWriteSerializer(payment, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        before = edit_snapshot(payment)
        before_applications = applications_snapshot(payment)
        try:
            with transaction.atomic():
                payment = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Payment number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        payment = get_payment_queryset(request.user).get(pk=payment.pk)
        log_update(payment, request.user, before, before_applications)
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
        for application in list(payment.applications.select_related("invoice")):
            reverse_application(application, payment=payment)
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
                    "unapplied": queryset.filter(
                        amount_applied__lt=F("amount"),
                        voided_at__isnull=True,
                    ).count(),
                    "applied": queryset.filter(
                        amount_applied__gte=F("amount"),
                        voided_at__isnull=True,
                    ).count(),
                    "void": queryset.filter(voided_at__isnull=False).count(),
                },
                "templates": template_options(PaymentReceived.Template.STANDARD),
                "actions": [
                    {"key": "save", "label": "Save", "path": "/api/payments-received/"},
                    {"key": "refresh", "label": "Refresh", "path": "/api/payments-received/refresh/"},
                    {"key": "export", "label": "Export Payments", "path": "/api/payments-received/export/"},
                    {"key": "apply", "label": "Apply to Invoice", "path": "/api/payments-received/apply/"},
                    {"key": "unapply", "label": "Unapply", "path": "/api/payments-received/unapply/"},
                    {"key": "edit", "label": "Edit", "path": "/api/payments-received/form/"},
                    {"key": "history", "label": "Payment History", "path": "/api/payments-received/history/"},
                    {"key": "void", "label": "Void", "path": "/api/payments-received/void/"},
                    {"key": "change_template", "label": "Change Template", "path": "/api/payments-received/template/"},
                    {"key": "download_pdf", "label": "Download PDF", "path": "/api/payments-received/pdf/"},
                    {"key": "preview", "label": "Preview", "path": "/api/payments-received/pdf/?inline=true"},
                    {"key": "print", "label": "Print", "path": "/api/payments-received/pdf/?inline=true"},
                    {"key": "email", "label": "Send Email", "path": "/api/payments-received/email/"},
                    {"key": "delete", "label": "Delete", "path": "/api/payments-received/"},
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
            data["payment_invoices"] = payment_invoices(payment)
            data["amount_summary"] = data["payment"]["amount_summary"]
            data["update_path"] = f"/api/payments-received/?payment_id={payment.id}"
            data["is_editable"] = not payment.is_void
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
        error_response = void_error(payment, "applied")
        if error_response:
            return error_response
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
            with transaction.atomic():
                _, applied_amount = apply_amount_to_invoice(payment, invoice, amount)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        log_activity(
            payment,
            f"Payment of {currency_amount(payment.currency, applied_amount)} "
            f"applied to {invoice.invoice_number}.",
            user=request.user,
        )
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
        error_response = void_error(payment, "unapplied")
        if error_response:
            return error_response
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
        invoice_number = application.invoice.invoice_number
        unapplied_amount = application.amount
        reverse_application(application)
        log_activity(
            payment,
            f"Payment of {currency_amount(payment.currency, unapplied_amount)} "
            f"unapplied from {invoice_number}.",
            user=request.user,
        )
        payment = get_payment_queryset(request.user).get(pk=payment.pk)
        return api_success(
            data=PaymentReceivedSerializer(payment).data,
            message="Payment unapplied successfully.",
        )


class PaymentReceivedHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment, error_response = get_payment_from_request(request)
        if error_response:
            return error_response

        queryset = payment.activities.select_related("created_by").order_by("created_at")
        response = paginate_queryset(
            request,
            queryset,
            serializer=PaymentReceivedActivitySerializer,
        )
        if response is not None:
            return response
        return api_success(data=[])


class PaymentReceivedVoidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment, error_response = get_payment_from_request(request)
        if error_response:
            return error_response
        if payment.is_void:
            return api_error(
                "Payment is already void.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        reason = str(request.data.get("reason") or request.data.get("void_reason") or "").strip()
        if len(reason) > 500:
            return api_error(
                "Validation error",
                errors={"reason": "Reason cannot be more than 500 characters."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for application in list(payment.applications.select_related("invoice")):
                reverse_application(application, payment=payment)
            payment.refresh_from_db()
            payment.voided_at = timezone.now()
            payment.void_reason = reason
            payment.voided_by = request.user
            payment.save(update_fields=["voided_at", "void_reason", "voided_by", "updated_at"])
            message = "Payment voided."
            if reason:
                message = f"Payment voided. Reason: {reason}"
            log_activity(payment, message, user=request.user)

        payment = refetch(request, payment)
        return api_success(
            data=PaymentReceivedSerializer(payment).data,
            message="Payment has been voided.",
        )


class PaymentReceivedTemplateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment, error_response = get_payment_from_request(request)
        if error_response:
            return error_response
        return api_success(
            data={
                "payment_id": payment.id,
                "template": payment.template,
                "template_label": payment.get_template_display(),
                "templates": template_options(payment.template),
            }
        )

    def post(self, request):
        payment, error_response = get_payment_from_request(request)
        if error_response:
            return error_response
        key = str(request.data.get("template") or "").strip().lower()
        allowed = [choice for choice, _ in PaymentReceived.Template.choices]
        if key not in allowed:
            return api_error(
                "Validation error",
                errors={"template": f"Allowed values: {', '.join(allowed)}."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if key != payment.template:
            payment.template = key
            payment.save(update_fields=["template", "updated_at"])
            log_activity(
                payment,
                f"Template changed to {payment.get_template_display()}.",
                user=request.user,
            )
        return api_success(
            data={
                "payment_id": payment.id,
                "template": payment.template,
                "template_label": payment.get_template_display(),
                "templates": template_options(payment.template),
            },
            message="Template updated successfully.",
        )

    def put(self, request):
        return self.post(request)

    def patch(self, request):
        return self.post(request)


class PaymentReceivedPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        payment, error_response = get_payment_from_request(request)
        if error_response:
            return error_response
        inline = str(request.query_params.get("inline", "")).strip().lower() == "true"
        response = HttpResponse(build_receipt_pdf(payment), content_type="application/pdf")
        disposition = "inline" if inline else "attachment"
        response["Content-Disposition"] = f'{disposition}; filename="{receipt_filename(payment)}"'
        return response


class PaymentReceivedEmailView(ThrottledResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        if self.request.method == "POST":
            return [PaymentReceiptEmailThrottle()]
        return []

    def get(self, request):
        payment, error_response = get_payment_from_request(request)
        if error_response:
            return error_response
        return api_success(data=build_email_form(payment, request.user))

    def post(self, request):
        payment, error_response = get_payment_from_request(request)
        if error_response:
            return error_response
        error_response = void_error(payment, "emailed")
        if error_response:
            return error_response

        errors = {}
        to = parse_recipients(request.data.get("to"), "to", errors, required=True)
        cc = parse_recipients(request.data.get("cc"), "cc", errors)
        bcc = parse_recipients(request.data.get("bcc"), "bcc", errors)
        form = build_email_form(payment, request.user)
        subject = str(request.data.get("subject") or form["subject"]).strip()
        if "\n" in subject or "\r" in subject:
            errors["subject"] = "Subject cannot contain line breaks."
        elif len(subject) > 255:
            errors["subject"] = "Subject cannot be more than 255 characters."
        body = str(request.data.get("body") or form["body"])
        attach_pdf = request.data.get("attach_pdf", True)
        if isinstance(attach_pdf, str):
            attach_pdf = attach_pdf.strip().lower() not in ("false", "0", "no")
        if errors:
            return api_error("Validation error", errors=errors)

        try:
            send_receipt_email(payment, request.user, to, cc, bcc, subject, body, bool(attach_pdf))
        except Exception:
            logger.exception("Failed to send payment receipt %s", payment.id)
            return api_error(
                "Could not send the email. Check the email settings and try again.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        log_activity(
            payment,
            f"Payment receipt emailed to {', '.join(to)}.",
            user=request.user,
        )
        return api_success(
            data={
                "payment_id": payment.id,
                "to": to,
                "cc": cc,
                "bcc": bcc,
                "subject": subject,
                "attach_pdf": bool(attach_pdf),
                "attachment_name": receipt_filename(payment) if attach_pdf else None,
            },
            message="Payment receipt has been sent.",
        )
