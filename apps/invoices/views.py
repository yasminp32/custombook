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

from apps.accounts.countries import get_states_for_country
from apps.accounts.responses import api_error, api_success
from apps.customers.constants import PAYMENT_TERMS
from apps.customers.models import Customer
from apps.invoices.filters import (
    INVOICE_STATUS_FILTERS,
    INVOICE_TAB_FILTERS,
    InvoiceFilter,
    overdue_q,
)
from apps.invoices.models import Invoice
from apps.invoices.serializers import (
    INVOICE_TAX_TREATMENTS,
    InvoiceSerializer,
    InvoiceWriteSerializer,
    calculate_due_date,
    next_invoice_number,
)
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "invoice_date",
    "invoice_date": "invoice_date",
    "invoice_number": "invoice_number",
    "invoice#": "invoice_number",
    "customer_name": "customer__display_name",
    "amount": "total_amount",
    "total_amount": "total_amount",
    "due_date": "due_date",
}

UAE_EMIRATES = (
    "Dubai",
    "Abu Dhabi",
    "Sharjah",
    "Ajman",
    "Umm Al Quwain",
    "Ras Al Khaimah",
    "Fujairah",
)


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_invoice_queryset(user):
    return Invoice.objects.filter(organization__owner=user).select_related(
        "organization",
        "customer",
        "sales_order",
        "delivery_challan",
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


def get_invoice_id_param(request):
    invoice_id = (
        request.query_params.get("invoice_id")
        or request.query_params.get("id")
        or request.data.get("invoice_id")
        or request.data.get("id")
    )
    if not invoice_id:
        return None, api_error(
            "invoice_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(invoice_id, "invoice_id")


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


def filtered_invoice_queryset(request):
    queryset = get_invoice_queryset(request.user)
    invoice_filter = InvoiceFilter(request.query_params, queryset=queryset)
    if not invoice_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=invoice_filter.errors)
    queryset, error_response = apply_sorting(invoice_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def serialize_address(address):
    if not address:
        return None
    return {
        "attention": address.attention or "",
        "address_line1": address.address_line1 or "",
        "address_line2": address.address_line2 or "",
        "city": address.city or "",
        "state": address.state or "",
        "country": address.country or "",
        "postal_code": address.postal_code or "",
        "phone": address.phone or "",
    }


def customer_option(customer):
    billing = None
    shipping = None
    for row in customer.addresses.all():
        if row.address_type == "billing" and not billing:
            billing = row.address
        elif row.address_type == "shipping" and not shipping:
            shipping = row.address
    return {
        "customer_id": customer.id,
        "display_name": customer.display_name or customer.company_name or customer.name,
        "company_name": customer.company_name or "",
        "email": customer.email or "",
        "phone": customer.phone or "",
        "tax_treatment": customer.tax_treatment or "",
        "place_of_supply": customer.place_of_supply or "",
        "payment_terms": customer.payment_terms or "due_on_receipt",
        "currency": customer.currency or "INR",
        "billing_address": serialize_address(billing),
        "shipping_address": serialize_address(shipping),
        "customer_details_path": f"/api/customers/?customer_id={customer.id}",
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
        name = f"{owner.first_name} {owner.last_name}".strip() or owner.email
        rows.append({"salesperson_id": owner.id, "salesperson_name": name})
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


def place_of_supply_options(organization):
    country = (organization.country or "").upper() if organization else ""
    values = []
    if country == "AE":
        values.extend(UAE_EMIRATES)
        values.extend(get_states_for_country("IN"))
    elif country == "IN":
        values.extend(get_states_for_country("IN"))
        values.extend(UAE_EMIRATES)
    else:
        values.extend(UAE_EMIRATES)
        values.extend(get_states_for_country("IN"))
        extra = get_states_for_country(country)
        for state in extra:
            if state not in values:
                values.append(state)
    if organization and organization.state and organization.state not in values:
        values.insert(0, organization.state)
    return [{"key": value, "label": value} for value in values]


def invoice_counts(queryset):
    return {
        "all": queryset.count(),
        "draft": queryset.filter(status=Invoice.Status.DRAFT).count(),
        "sent": queryset.filter(status=Invoice.Status.SENT).exclude(overdue_q()).count(),
        "paid": queryset.filter(status=Invoice.Status.PAID).count(),
        "partially_paid": queryset.filter(status=Invoice.Status.PARTIALLY_PAID)
        .exclude(overdue_q())
        .count(),
        "overdue": queryset.filter(overdue_q()).count(),
        "cancelled": queryset.filter(status=Invoice.Status.CANCELLED).count(),
    }


def build_invoice_form(user, organization):
    queryset = get_invoice_queryset(user)
    customers = Customer.objects.filter(
        organization=organization,
        status=Customer.Status.ACTIVE,
    ).prefetch_related("addresses__address").order_by(
        "display_name",
        "company_name",
    )[:100]
    items = Item.objects.filter(
        organization=organization,
        sales_enabled=True,
        status=Item.Status.ACTIVE,
    ).order_by("name")[:100]
    today = date.today()
    next_number = next_invoice_number(organization)
    default_terms = "due_on_receipt"
    default_due = calculate_due_date(today, default_terms)
    default_tax_treatment = (
        "vat_registered" if organization and organization.country == "AE" else "gst_registered"
    )
    default_place = organization.state if organization and organization.state else (
        "Dubai" if organization and organization.country == "AE" else ""
    )
    return {
        "title": "New Invoice",
        "next_invoice_number": next_number,
        "defaults": {
            "invoice_number": next_number,
            "invoice_date": today.isoformat(),
            "invoice_date_label": today.strftime("%d %b %Y"),
            "due_date": default_due.isoformat(),
            "due_date_label": default_due.strftime("%d %b %Y"),
            "payment_terms": default_terms,
            "place_of_supply": default_place,
            "tax_treatment": default_tax_treatment,
            "tax_type": Invoice.TaxType.EXCLUSIVE,
            "subject": "",
            "customer_notes": "Thanks for your business.",
            "terms_and_conditions": "",
            "email_recipients": [],
            "payment_received": False,
            "total_amount": "0.00",
            "action": "save_as_draft",
        },
        "fields": {
            "customer_id": {
                "label": "Customer Name",
                "required": True,
                "placeholder": "Select Customer",
                "can_add": True,
                "add_path": "/api/customers/",
            },
            "tax_treatment": {"label": "Tax Treatment", "required": False},
            "place_of_supply": {"label": "Place Of Supply", "required": True},
            "invoice_number": {"label": "Invoice#", "required": True},
            "order_number": {"label": "Order Number", "required": False},
            "invoice_date": {"label": "Invoice Date", "required": True},
            "payment_terms": {"label": "Terms", "required": True},
            "due_date": {"label": "Due Date", "required": True},
            "salesperson": {
                "label": "Salesperson",
                "required": False,
                "placeholder": "Select or Add Salesperson",
            },
            "subject": {
                "label": "Subject",
                "required": False,
                "placeholder": "What is this invoice for?",
            },
            "tax_type": {"label": "Tax", "required": False},
            "line_items": {"label": "Add Line Item", "required": False},
            "customer_notes": {"label": "Customer Notes", "required": False},
            "terms_and_conditions": {"label": "Terms & Conditions", "required": False},
            "email_recipients": {
                "label": "Email Communications",
                "required": False,
                "placeholder": "name@example.com",
            },
            "payment_received": {
                "label": "I have received the payment",
                "required": False,
            },
            "attachments": {
                "label": "Attachments",
                "upload_path": "/api/attachments/",
            },
        },
        "customers": [customer_option(row) for row in customers],
        "items": [item_option(row) for row in items],
        "payment_terms": [{"key": key, "label": label} for key, label in PAYMENT_TERMS],
        "tax_treatments": [
            {"key": key, "label": label} for key, label in INVOICE_TAX_TREATMENTS
        ],
        "place_of_supply": place_of_supply_options(organization),
        "salespersons": salesperson_options(organization, queryset),
        "tax_types": [
            {"key": key, "label": label} for key, label in Invoice.TaxType.choices
        ],
        "counts": invoice_counts(queryset),
        "actions": [
            {
                "key": "save_as_draft",
                "label": "Save as Draft",
                "path": "/api/invoices/",
            },
            {
                "key": "save_and_send",
                "label": "Save and send",
                "path": "/api/invoices/",
            },
            {
                "key": "preview_invoice",
                "label": "Preview invoice",
                "path": "/api/invoices/",
            },
        ],
        "create_path": "/api/invoices/",
        "attachments_path": "/api/attachments/",
    }


def success_message(invoice):
    status_value = invoice.effective_status()
    if status_value == Invoice.Status.PAID:
        return "Invoice marked as paid."
    if status_value == Invoice.Status.SENT:
        return "Invoice saved and sent."
    if status_value == "overdue":
        return "Invoice saved and sent."
    return "Invoice saved as draft."


class InvoiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        invoice_id = request.query_params.get("invoice_id") or request.query_params.get("id")
        if invoice_id:
            parsed_id, error_response = parse_uuid(invoice_id, "invoice_id")
            if error_response:
                return error_response
            invoice = get_invoice_queryset(request.user).filter(pk=parsed_id).first()
            if not invoice:
                return api_error("Invoice not found.", status_code=status.HTTP_404_NOT_FOUND)
            return api_success(data=InvoiceSerializer(invoice).data)

        queryset, error_response = filtered_invoice_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=InvoiceSerializer)
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
                "Organization not found. Complete organization setup before creating invoices.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = InvoiceWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            invoice = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Invoice number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        invoice = get_invoice_queryset(request.user).get(pk=invoice.pk)
        return api_success(
            data=InvoiceSerializer(invoice).data,
            message=success_message(invoice),
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        invoice_id, error_response = get_invoice_id_param(request)
        if error_response:
            return error_response
        invoice = get_invoice_queryset(request.user).filter(pk=invoice_id).first()
        if not invoice:
            return api_error("Invoice not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = InvoiceWriteSerializer(invoice, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            invoice = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Invoice number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        invoice = get_invoice_queryset(request.user).get(pk=invoice.pk)
        return api_success(
            data=InvoiceSerializer(invoice).data,
            message="Invoice updated successfully.",
        )

    def delete(self, request):
        invoice_id, error_response = get_invoice_id_param(request)
        if error_response:
            return error_response
        invoice = get_invoice_queryset(request.user).filter(pk=invoice_id).first()
        if not invoice:
            return api_error("Invoice not found.", status_code=status.HTTP_404_NOT_FOUND)
        if invoice.status in (Invoice.Status.PAID, Invoice.Status.SENT, Invoice.Status.PARTIALLY_PAID):
            return api_error(
                "Sent or paid invoices cannot be deleted. Cancel them instead.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        invoice.delete()
        return api_success(message="Invoice deleted successfully.")


class InvoiceOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_invoice_queryset(request.user)
        organization = resolve_organization(
            request.user,
            request.query_params.get("organization_id"),
        )
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in INVOICE_TAB_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in INVOICE_STATUS_FILTERS
                ],
                "tax_treatments": [
                    {"key": key, "label": label} for key, label in INVOICE_TAX_TREATMENTS
                ],
                "place_of_supply": place_of_supply_options(organization),
                "payment_terms": [
                    {"key": key, "label": label} for key, label in PAYMENT_TERMS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "invoice_number", "label": "Invoice#"},
                    {"key": "customer_name", "label": "Customer Name"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/invoices/form/",
                "counts": invoice_counts(queryset),
                "actions": [
                    {"key": "save_as_draft", "label": "Save as Draft", "path": "/api/invoices/"},
                    {"key": "save_and_send", "label": "Save and send", "path": "/api/invoices/"},
                    {"key": "refresh", "label": "Refresh", "path": "/api/invoices/refresh/"},
                    {"key": "export", "label": "Export Invoices", "path": "/api/invoices/export/"},
                    {"key": "send", "label": "Send", "path": "/api/invoices/send/"},
                    {"key": "mark_paid", "label": "Mark as Paid", "path": "/api/invoices/mark-paid/"},
                    {
                        "key": "mark_partially_paid",
                        "label": "Mark as Partially Paid",
                        "path": "/api/invoices/mark-partially-paid/",
                    },
                    {"key": "cancel", "label": "Cancel", "path": "/api/invoices/cancel/"},
                ],
            }
        )


class InvoiceFormView(APIView):
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
        data = build_invoice_form(request.user, organization)
        invoice_id = request.query_params.get("invoice_id") or request.query_params.get("id")
        if invoice_id:
            parsed_id, error_response = parse_uuid(invoice_id, "invoice_id")
            if error_response:
                return error_response
            invoice = get_invoice_queryset(request.user).filter(pk=parsed_id).first()
            if not invoice:
                return api_error("Invoice not found.", status_code=status.HTTP_404_NOT_FOUND)
            data["title"] = "Edit Invoice"
            data["invoice"] = InvoiceSerializer(invoice).data
        return api_success(data=data)


class InvoiceRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_invoice_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=InvoiceSerializer)
        if response is not None:
            response.data["message"] = "Invoices refreshed."
            return response
        return api_success(data=[], message="Invoices refreshed.")


class InvoiceExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_invoice_queryset(request)
        if error_response:
            return error_response
        rows = InvoiceSerializer(queryset, many=True).data
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
                    "invoice_id",
                    "invoice_number",
                    "customer_name",
                    "invoice_date",
                    "due_date",
                    "status",
                    "total_amount",
                    "amount_paid",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "invoice_id": row["invoice_id"],
                        "invoice_number": row["invoice_number"],
                        "customer_name": row["customer_name"],
                        "invoice_date": row["invoice_date"],
                        "due_date": row["due_date"],
                        "status": row["status"],
                        "total_amount": row["total_amount"],
                        "amount_paid": row["amount_paid"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="invoices.csv"'
            return response
        return api_success(
            data={"count": len(rows), "invoices": rows},
            message="Invoices exported successfully.",
        )


class InvoiceSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        invoice_id, error_response = get_invoice_id_param(request)
        if error_response:
            return error_response
        invoice = get_invoice_queryset(request.user).filter(pk=invoice_id).first()
        if not invoice:
            return api_error("Invoice not found.", status_code=status.HTTP_404_NOT_FOUND)
        if invoice.status in (Invoice.Status.CANCELLED, Invoice.Status.PAID):
            return api_error(
                "Paid or cancelled invoices cannot be sent.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not invoice.lines.exists():
            return api_error(
                "Add at least one line item before sending the invoice.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        invoice.status = Invoice.Status.SENT
        if not invoice.sent_at:
            invoice.sent_at = timezone.now()
        invoice.save(update_fields=["status", "sent_at", "updated_at"])
        invoice = get_invoice_queryset(request.user).get(pk=invoice.pk)
        return api_success(
            data=InvoiceSerializer(invoice).data,
            message="Invoice sent successfully.",
        )


class InvoiceMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        invoice_id, error_response = get_invoice_id_param(request)
        if error_response:
            return error_response
        invoice = get_invoice_queryset(request.user).filter(pk=invoice_id).first()
        if not invoice:
            return api_error("Invoice not found.", status_code=status.HTTP_404_NOT_FOUND)
        if invoice.status == Invoice.Status.CANCELLED:
            return api_error(
                "Cancelled invoices cannot be marked as paid.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not invoice.lines.exists():
            return api_error(
                "Add at least one line item before marking as paid.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        invoice.status = Invoice.Status.PAID
        invoice.payment_received = True
        invoice.amount_paid = invoice.total_amount
        if not invoice.paid_at:
            invoice.paid_at = timezone.now()
        invoice.save(
            update_fields=[
                "status",
                "payment_received",
                "amount_paid",
                "paid_at",
                "updated_at",
            ]
        )
        invoice = get_invoice_queryset(request.user).get(pk=invoice.pk)
        return api_success(
            data=InvoiceSerializer(invoice).data,
            message="Invoice marked as paid.",
        )


class InvoiceMarkPartiallyPaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        invoice_id, error_response = get_invoice_id_param(request)
        if error_response:
            return error_response
        invoice = get_invoice_queryset(request.user).filter(pk=invoice_id).first()
        if not invoice:
            return api_error("Invoice not found.", status_code=status.HTTP_404_NOT_FOUND)
        if invoice.status in (Invoice.Status.CANCELLED, Invoice.Status.PAID, Invoice.Status.DRAFT):
            return api_error(
                "Only sent invoices can be marked as partially paid.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        amount_paid = request.data.get("amount_paid")
        if amount_paid is None:
            return api_error(
                "amount_paid is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from decimal import Decimal

            paid = Decimal(str(amount_paid))
        except Exception:
            return api_error(
                "amount_paid must be a valid number.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if paid <= 0:
            return api_error(
                "amount_paid must be greater than zero.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if paid >= invoice.total_amount:
            invoice.status = Invoice.Status.PAID
            invoice.payment_received = True
            invoice.amount_paid = invoice.total_amount
            if not invoice.paid_at:
                invoice.paid_at = timezone.now()
            invoice.save(
                update_fields=[
                    "status",
                    "payment_received",
                    "amount_paid",
                    "paid_at",
                    "updated_at",
                ]
            )
            invoice = get_invoice_queryset(request.user).get(pk=invoice.pk)
            return api_success(
                data=InvoiceSerializer(invoice).data,
                message="Invoice marked as paid.",
            )
        invoice.status = Invoice.Status.PARTIALLY_PAID
        invoice.payment_received = False
        invoice.amount_paid = paid
        invoice.save(update_fields=["status", "payment_received", "amount_paid", "updated_at"])
        invoice = get_invoice_queryset(request.user).get(pk=invoice.pk)
        return api_success(
            data=InvoiceSerializer(invoice).data,
            message="Invoice marked as partially paid.",
        )


class InvoiceCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        invoice_id, error_response = get_invoice_id_param(request)
        if error_response:
            return error_response
        invoice = get_invoice_queryset(request.user).filter(pk=invoice_id).first()
        if not invoice:
            return api_error("Invoice not found.", status_code=status.HTTP_404_NOT_FOUND)
        if invoice.status in (Invoice.Status.PAID, Invoice.Status.CANCELLED):
            return api_error(
                "This invoice cannot be cancelled.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        invoice.status = Invoice.Status.CANCELLED
        if not invoice.cancelled_at:
            invoice.cancelled_at = timezone.now()
        invoice.save(update_fields=["status", "cancelled_at", "updated_at"])
        invoice = get_invoice_queryset(request.user).get(pk=invoice.pk)
        return api_success(
            data=InvoiceSerializer(invoice).data,
            message="Invoice cancelled successfully.",
        )
