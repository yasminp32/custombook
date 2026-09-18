import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from apps.attachments.models import Attachment
from apps.customers.constants import PAYMENT_TERM_ALIASES, PAYMENT_TERMS, TAX_TREATMENT_ALIASES
from apps.customers.models import Customer
from apps.delivery_challans.models import DeliveryChallan
from apps.invoices.models import Invoice, InvoiceLine
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.sales_orders.models import SalesOrder

ZERO = Decimal("0.00")
INVOICE_NUMBER_RE = re.compile(r"^INV-(\d+)$", re.IGNORECASE)
DEFAULT_CUSTOMER_NOTES = "Thanks for your business."

INVOICE_TAX_TREATMENT_ALIASES = {
    **TAX_TREATMENT_ALIASES,
    "vat_registered": "vat_registered",
    "vat registered": "vat_registered",
}

INVOICE_TAX_TREATMENTS = (
    ("vat_registered", "VAT Registered"),
    ("gst_registered", "GST Registered"),
    ("non_gst_registered", "Non GST Registered"),
    ("gst_registered_composition", "GST Registered - Composition"),
    ("consumer", "Consumer"),
    ("overseas", "Overseas"),
    ("sez", "SEZ"),
)

STATUS_LABELS = {
    Invoice.Status.DRAFT: "DRAFT",
    Invoice.Status.SENT: "SENT",
    Invoice.Status.PAID: "PAID",
    Invoice.Status.PARTIALLY_PAID: "PARTIALLY PAID",
    Invoice.Status.CANCELLED: "CANCELLED",
    "overdue": "OVERDUE",
}

ALLOWED_STATUS_TRANSITIONS = {
    Invoice.Status.DRAFT: {
        Invoice.Status.DRAFT,
        Invoice.Status.SENT,
        Invoice.Status.PAID,
        Invoice.Status.CANCELLED,
    },
    Invoice.Status.SENT: {
        Invoice.Status.SENT,
        Invoice.Status.PAID,
        Invoice.Status.PARTIALLY_PAID,
        Invoice.Status.CANCELLED,
    },
    Invoice.Status.PARTIALLY_PAID: {
        Invoice.Status.PARTIALLY_PAID,
        Invoice.Status.PAID,
        Invoice.Status.CANCELLED,
    },
    Invoice.Status.PAID: {
        Invoice.Status.PAID,
    },
    Invoice.Status.CANCELLED: {
        Invoice.Status.CANCELLED,
    },
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def next_invoice_number(organization):
    numbers = Invoice.objects.filter(organization=organization).values_list(
        "invoice_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = INVOICE_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"INV-{highest + 1:06d}"


def calculate_due_date(invoice_date, payment_terms):
    invoice_date = invoice_date or date.today()
    key = (payment_terms or "due_on_receipt").strip().lower().replace(" ", "_")
    days = {
        "due_on_receipt": 0,
        "net_15": 15,
        "net_30": 30,
        "net_45": 45,
        "net_60": 60,
    }
    if key in days:
        return invoice_date + timedelta(days=days[key])
    if key == "due_end_of_month":
        last_day = monthrange(invoice_date.year, invoice_date.month)[1]
        return invoice_date.replace(day=last_day)
    if key == "due_end_of_next_month":
        if invoice_date.month == 12:
            year, month = invoice_date.year + 1, 1
        else:
            year, month = invoice_date.year, invoice_date.month + 1
        last_day = monthrange(year, month)[1]
        return date(year, month, last_day)
    return invoice_date


def source_lines(source):
    return [
        {
            "item_id": line.item_id,
            "name": line.name,
            "description": line.description,
            "quantity": line.quantity,
            "rate": line.rate,
            "tax": line.tax,
            "sort_order": line.sort_order,
        }
        for line in source.lines.all()
    ]


class InvoiceLineSerializer(serializers.ModelSerializer):
    line_id = serializers.UUIDField(source="id", read_only=True)
    item_id = serializers.UUIDField(read_only=True, allow_null=True)
    quantity = serializers.SerializerMethodField()
    rate = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceLine
        fields = (
            "line_id",
            "item_id",
            "name",
            "description",
            "quantity",
            "rate",
            "tax",
            "amount",
            "sort_order",
        )
        read_only_fields = fields

    def get_quantity(self, obj):
        return money(obj.quantity)

    def get_rate(self, obj):
        return money(obj.rate)

    def get_amount(self, obj):
        return money(obj.amount)


class InvoiceLineWriteSerializer(serializers.Serializer):
    line_id = serializers.UUIDField(required=False)
    item_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        default=1,
    )
    rate = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        default=0,
    )
    tax = serializers.CharField(required=False, allow_blank=True)
    sort_order = serializers.IntegerField(required=False, min_value=0)


class InvoiceSerializer(serializers.ModelSerializer):
    invoice_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_name = serializers.SerializerMethodField()
    sales_order_id = serializers.UUIDField(read_only=True, allow_null=True)
    delivery_challan_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    stored_status = serializers.CharField(source="status", read_only=True)
    status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    payment_terms_label = serializers.SerializerMethodField()
    tax_treatment_label = serializers.SerializerMethodField()
    tax_type_label = serializers.CharField(source="get_tax_type_display", read_only=True)
    invoice_date_label = serializers.SerializerMethodField()
    due_date_label = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    balance_due = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    email_recipients = serializers.SerializerMethodField()
    line_items = InvoiceLineSerializer(source="lines", many=True, read_only=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            "invoice_id",
            "organization_id",
            "customer_id",
            "customer_name",
            "sales_order_id",
            "delivery_challan_id",
            "invoice_number",
            "order_number",
            "invoice_date",
            "invoice_date_label",
            "due_date",
            "due_date_label",
            "payment_terms",
            "payment_terms_label",
            "place_of_supply",
            "tax_treatment",
            "tax_treatment_label",
            "salesperson_id",
            "salesperson_name",
            "subject",
            "tax_type",
            "tax_type_label",
            "customer_notes",
            "terms_and_conditions",
            "email_recipients",
            "payment_received",
            "stored_status",
            "status",
            "status_label",
            "is_overdue",
            "sent_at",
            "paid_at",
            "cancelled_at",
            "amount_paid",
            "balance_due",
            "total_amount",
            "currency",
            "line_items",
            "attachments",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_customer_name(self, obj):
        if not obj.customer:
            return ""
        return obj.customer.display_name or obj.customer.company_name or obj.customer.name

    def get_status(self, obj):
        return obj.effective_status()

    def get_status_label(self, obj):
        return STATUS_LABELS.get(obj.effective_status(), obj.effective_status().upper())

    def get_is_overdue(self, obj):
        return obj.is_overdue()

    def get_invoice_date_label(self, obj):
        if not obj.invoice_date:
            return ""
        return obj.invoice_date.strftime("%d %b %Y")

    def get_due_date_label(self, obj):
        if not obj.due_date:
            return ""
        return f"Due {obj.due_date.strftime('%d %b %Y')}"

    def get_payment_terms_label(self, obj):
        mapping = dict(PAYMENT_TERMS)
        return mapping.get(obj.payment_terms, obj.payment_terms or "")

    def get_tax_treatment_label(self, obj):
        mapping = dict(INVOICE_TAX_TREATMENTS)
        return mapping.get(obj.tax_treatment, obj.tax_treatment or "")

    def get_total_amount(self, obj):
        return money(obj.total_amount)

    def get_amount_paid(self, obj):
        return money(obj.amount_paid)

    def get_balance_due(self, obj):
        total = Decimal(obj.total_amount or 0)
        paid = Decimal(obj.amount_paid or 0)
        return money(max(total - paid, ZERO))

    def get_currency(self, obj):
        if obj.currency:
            return obj.currency
        if obj.customer and getattr(obj.customer, "currency", None):
            return obj.customer.currency
        if obj.organization and obj.organization.currency:
            return obj.organization.currency
        return "INR"

    def get_email_recipients(self, obj):
        recipients = obj.email_recipients or []
        if isinstance(recipients, list):
            return [str(item).strip() for item in recipients if str(item).strip()]
        return []

    def get_attachments(self, obj):
        rows = Attachment.objects.filter(
            attachable_type="invoice",
            attachable_id=obj.id,
        ).order_by("-created_at")
        return [
            {
                "attachment_id": row.id,
                "file_name": row.file_name,
                "mime_type": row.mime_type,
                "file_size": row.file_size,
            }
            for row in rows
        ]


class InvoiceWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    sales_order_id = serializers.UUIDField(required=False, allow_null=True)
    delivery_challan_id = serializers.UUIDField(required=False, allow_null=True)
    invoice_number = serializers.CharField(required=False, allow_blank=True)
    invoice_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)
    email_recipients = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    line_items = InvoiceLineWriteSerializer(many=True, required=False)
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Invoice
        fields = (
            "organization_id",
            "customer_id",
            "sales_order_id",
            "delivery_challan_id",
            "invoice_number",
            "order_number",
            "invoice_date",
            "due_date",
            "payment_terms",
            "place_of_supply",
            "tax_treatment",
            "salesperson_id",
            "salesperson_name",
            "subject",
            "tax_type",
            "customer_notes",
            "terms_and_conditions",
            "email_recipients",
            "payment_received",
            "amount_paid",
            "status",
            "currency",
            "action",
            "line_items",
            "attachment_ids",
        )

    def validate_tax_type(self, value):
        if not value:
            return Invoice.TaxType.EXCLUSIVE
        key = str(value).strip().lower()
        aliases = {"exclusive": "exclusive", "inclusive": "inclusive"}
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid tax type. Allowed values: exclusive, inclusive."
            )
        return aliases[key]

    def validate_payment_terms(self, value):
        if not value:
            return "due_on_receipt"
        key = str(value).strip().lower().replace(" ", "_")
        label_key = str(value).strip().lower()
        if label_key in PAYMENT_TERM_ALIASES:
            return PAYMENT_TERM_ALIASES[label_key]
        if key in PAYMENT_TERM_ALIASES:
            return PAYMENT_TERM_ALIASES[key]
        allowed = {choice[0] for choice in PAYMENT_TERMS}
        if key not in allowed:
            raise serializers.ValidationError(
                f"Invalid payment terms. Allowed values: {', '.join(choice[0] for choice in PAYMENT_TERMS)}."
            )
        return key

    def validate_tax_treatment(self, value):
        if not value:
            return ""
        key = str(value).strip().lower()
        mapped = INVOICE_TAX_TREATMENT_ALIASES.get(key) or INVOICE_TAX_TREATMENT_ALIASES.get(
            key.replace(" ", "_")
        )
        if not mapped:
            raise serializers.ValidationError(
                "Invalid tax treatment. Allowed values: "
                f"{', '.join(choice[0] for choice in INVOICE_TAX_TREATMENTS)}."
            )
        return mapped

    def validate_salesperson_name(self, value):
        return (value or "").strip()

    def validate_place_of_supply(self, value):
        return (value or "").strip()

    def validate_status(self, value):
        if not value:
            return Invoice.Status.DRAFT
        key = str(value).strip().lower().replace(" ", "_")
        if key == "overdue":
            return Invoice.Status.SENT
        if key not in Invoice.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(Invoice.Status.values)}."
            )
        return key

    def validate_action(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save_as_draft": "save_as_draft",
            "draft": "save_as_draft",
            "save_and_send": "save_and_send",
            "send": "save_and_send",
            "save_as_sent": "save_and_send",
            "save_as_paid": "save_as_paid",
            "paid": "save_as_paid",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save_as_draft, save_and_send, save_as_paid."
            )
        return aliases[key]

    def validate_invoice_number(self, value):
        return (value or "").strip().upper()

    def validate_email_recipients(self, value):
        emails = []
        for item in value or []:
            email = str(item).strip()
            if not email:
                continue
            try:
                validate_email(email)
            except DjangoValidationError:
                raise serializers.ValidationError(f"Invalid email: {email}")
            emails.append(email)
        return emails

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        action = attrs.pop("action", "") or ""
        payment_received = attrs.get("payment_received")
        if payment_received is None and self.instance:
            payment_received = self.instance.payment_received
        payment_received = bool(payment_received)

        if action == "save_as_draft":
            attrs["status"] = Invoice.Status.DRAFT
        elif action == "save_and_send":
            attrs["status"] = Invoice.Status.SENT
        elif action == "save_as_paid":
            attrs["status"] = Invoice.Status.PAID
            attrs["payment_received"] = True
            payment_received = True

        if payment_received and attrs.get("status") in (
            None,
            Invoice.Status.DRAFT,
            Invoice.Status.SENT,
            Invoice.Status.PARTIALLY_PAID,
        ):
            attrs["status"] = Invoice.Status.PAID
            attrs["payment_received"] = True

        customer_id = attrs.get("customer_id")
        if not self.partial and not customer_id and not self.instance:
            raise serializers.ValidationError({"customer_id": "Customer is required."})
        if customer_id and not Customer.objects.filter(pk=customer_id).exists():
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        sales_order_id = attrs.get("sales_order_id")
        if sales_order_id and not SalesOrder.objects.filter(pk=sales_order_id).exists():
            raise serializers.ValidationError({"sales_order_id": "Sales order not found."})

        delivery_challan_id = attrs.get("delivery_challan_id")
        if delivery_challan_id and not DeliveryChallan.objects.filter(pk=delivery_challan_id).exists():
            raise serializers.ValidationError(
                {"delivery_challan_id": "Delivery challan not found."}
            )

        if not attrs.get("invoice_date") and not self.partial and not self.instance:
            attrs["invoice_date"] = date.today()

        invoice_date = attrs.get("invoice_date")
        if invoice_date is None and self.instance:
            invoice_date = self.instance.invoice_date
        payment_terms = attrs.get("payment_terms")
        if payment_terms is None and self.instance:
            payment_terms = self.instance.payment_terms
        if not attrs.get("due_date") and (not self.partial or not self.instance):
            attrs["due_date"] = calculate_due_date(invoice_date, payment_terms)
        elif "payment_terms" in attrs and "due_date" not in attrs:
            attrs["due_date"] = calculate_due_date(invoice_date, payment_terms)

        current_status = self.instance.status if self.instance else Invoice.Status.DRAFT
        next_status = attrs.get("status", current_status) or Invoice.Status.DRAFT
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if next_status not in allowed:
            raise serializers.ValidationError(
                {
                    "status": (
                        f"Cannot change status from {current_status} to {next_status}."
                    )
                }
            )

        lines = attrs.get("line_items")
        needs_lines = next_status in (
            Invoice.Status.SENT,
            Invoice.Status.PAID,
            Invoice.Status.PARTIALLY_PAID,
        )
        if needs_lines and lines is not None and not lines:
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before sending or marking as paid."}
            )
        if needs_lines and lines is None and not self.instance:
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before sending or marking as paid."}
            )
        if (
            needs_lines
            and lines is None
            and self.instance
            and not self.instance.lines.exists()
        ):
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before sending or marking as paid."}
            )
        return attrs

    def _replace_lines(self, invoice, lines, organization):
        invoice.lines.all().delete()
        total = ZERO
        for index, line in enumerate(lines or []):
            item = None
            item_id = line.get("item_id")
            if item_id:
                item = Item.objects.filter(pk=item_id, organization=organization).first()
                if not item:
                    raise serializers.ValidationError(
                        {"line_items": {index: {"item_id": "Item not found."}}}
                    )
            name = (line.get("name") or "").strip()
            if not name and item:
                name = item.name
            quantity = line.get("quantity")
            if quantity is None:
                quantity = Decimal("1")
            rate = line.get("rate")
            if rate is None:
                rate = item.selling_price if item and item.selling_price is not None else ZERO
            amount = (quantity or ZERO) * (rate or ZERO)
            InvoiceLine.objects.create(
                invoice=invoice,
                item=item,
                name=name,
                description=(line.get("description") or "").strip(),
                quantity=quantity,
                rate=rate,
                tax=(line.get("tax") or "").strip(),
                amount=amount,
                sort_order=line.get("sort_order") if line.get("sort_order") is not None else index,
            )
            total += amount
        invoice.total_amount = total
        if invoice.status == Invoice.Status.PAID:
            invoice.amount_paid = total
            invoice.payment_received = True
        invoice.save(update_fields=["total_amount", "amount_paid", "payment_received", "updated_at"])

    def _link_attachments(self, invoice, attachment_ids, organization):
        if attachment_ids is None:
            return
        Attachment.objects.filter(
            attachable_type="invoice",
            attachable_id=invoice.id,
        ).update(attachable_type="", attachable_id=None)
        for attachment_id in attachment_ids:
            attachment = Attachment.objects.filter(
                pk=attachment_id,
                organization=organization,
            ).first()
            if not attachment:
                raise serializers.ValidationError(
                    {"attachment_ids": "Attachment not found."}
                )
            attachment.attachable_type = "invoice"
            attachment.attachable_id = invoice.id
            attachment.save(update_fields=["attachable_type", "attachable_id", "updated_at"])

    def _apply_status_timestamps(self, data, instance=None):
        status_value = data.get("status")
        if status_value == Invoice.Status.SENT and not (instance and instance.sent_at):
            data["sent_at"] = timezone.now()
        if status_value == Invoice.Status.PAID:
            if not (instance and instance.paid_at):
                data["paid_at"] = timezone.now()
            data["payment_received"] = True
        if status_value == Invoice.Status.CANCELLED and not (
            instance and instance.cancelled_at
        ):
            data["cancelled_at"] = timezone.now()
        return data

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        customer_id = validated_data.pop("customer_id", None)
        sales_order_id = validated_data.pop("sales_order_id", None)
        delivery_challan_id = validated_data.pop("delivery_challan_id", None)
        lines = validated_data.pop("line_items", None)
        attachment_ids = validated_data.pop("attachment_ids", None)

        customer = Customer.objects.filter(pk=customer_id, organization=organization).first()
        if not customer:
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        sales_order = None
        if sales_order_id:
            sales_order = SalesOrder.objects.filter(
                pk=sales_order_id,
                organization=organization,
            ).first()
            if not sales_order:
                raise serializers.ValidationError({"sales_order_id": "Sales order not found."})
            if lines is None:
                lines = source_lines(sales_order)
            if not validated_data.get("order_number"):
                validated_data["order_number"] = sales_order.sales_order_number
            if not validated_data.get("salesperson_id"):
                validated_data["salesperson_id"] = sales_order.salesperson_id
            if not validated_data.get("salesperson_name"):
                validated_data["salesperson_name"] = sales_order.salesperson_name
            if not validated_data.get("payment_terms"):
                validated_data["payment_terms"] = sales_order.payment_terms or "due_on_receipt"
            if not validated_data.get("subject"):
                validated_data["subject"] = sales_order.subject
            if not validated_data.get("customer_notes"):
                validated_data["customer_notes"] = sales_order.customer_notes
            if not validated_data.get("terms_and_conditions"):
                validated_data["terms_and_conditions"] = sales_order.terms_and_conditions

        delivery_challan = None
        if delivery_challan_id:
            delivery_challan = DeliveryChallan.objects.filter(
                pk=delivery_challan_id,
                organization=organization,
            ).first()
            if not delivery_challan:
                raise serializers.ValidationError(
                    {"delivery_challan_id": "Delivery challan not found."}
                )
            if lines is None:
                lines = source_lines(delivery_challan)

        if not validated_data.get("place_of_supply"):
            validated_data["place_of_supply"] = customer.place_of_supply or (
                organization.state if organization else ""
            )
        if not validated_data.get("tax_treatment"):
            validated_data["tax_treatment"] = customer.tax_treatment or (
                "vat_registered" if organization and organization.country == "AE" else ""
            )
        if not validated_data.get("payment_terms"):
            validated_data["payment_terms"] = customer.payment_terms or "due_on_receipt"
        if not validated_data.get("due_date"):
            validated_data["due_date"] = calculate_due_date(
                validated_data.get("invoice_date"),
                validated_data.get("payment_terms"),
            )
        if not validated_data.get("customer_notes"):
            validated_data["customer_notes"] = DEFAULT_CUSTOMER_NOTES

        requested_number = (validated_data.get("invoice_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and Invoice.objects.filter(
                organization=organization,
                invoice_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["invoice_number"] = next_invoice_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = customer.currency or (
                organization.currency if organization else "INR"
            ) or "INR"
        validated_data = self._apply_status_timestamps(validated_data)
        invoice = Invoice.objects.create(
            organization=organization,
            customer=customer,
            sales_order=sales_order,
            delivery_challan=delivery_challan,
            created_by=created_by,
            **validated_data,
        )
        self._replace_lines(invoice, lines or [], organization)
        self._link_attachments(invoice, attachment_ids, organization)
        return invoice

    def update(self, instance, validated_data):
        if instance.status in (Invoice.Status.PAID, Invoice.Status.CANCELLED):
            raise serializers.ValidationError(
                {"status": "Paid or cancelled invoices cannot be updated."}
            )
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        customer_id = validated_data.pop("customer_id", None)
        sales_order_id = validated_data.pop("sales_order_id", None)
        delivery_challan_id = validated_data.pop("delivery_challan_id", None)
        lines = validated_data.pop("line_items", None)
        attachment_ids = validated_data.pop("attachment_ids", None)
        if customer_id:
            customer = Customer.objects.filter(
                pk=customer_id,
                organization=instance.organization,
            ).first()
            if not customer:
                raise serializers.ValidationError({"customer_id": "Customer not found."})
            instance.customer = customer
        if sales_order_id:
            sales_order = SalesOrder.objects.filter(
                pk=sales_order_id,
                organization=instance.organization,
            ).first()
            if not sales_order:
                raise serializers.ValidationError({"sales_order_id": "Sales order not found."})
            instance.sales_order = sales_order
        if delivery_challan_id:
            delivery_challan = DeliveryChallan.objects.filter(
                pk=delivery_challan_id,
                organization=instance.organization,
            ).first()
            if not delivery_challan:
                raise serializers.ValidationError(
                    {"delivery_challan_id": "Delivery challan not found."}
                )
            instance.delivery_challan = delivery_challan
        validated_data = self._apply_status_timestamps(validated_data, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if lines is not None:
            self._replace_lines(instance, lines, instance.organization)
        if attachment_ids is not None:
            self._link_attachments(instance, attachment_ids, instance.organization)
        return instance
