import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.attachments.models import Attachment
from apps.customers.constants import PAYMENT_TERM_ALIASES, PAYMENT_TERMS
from apps.customers.models import Customer
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.quotes.models import Quote
from apps.sales_orders.models import SalesOrder, SalesOrderLine

ZERO = Decimal("0.00")
SALES_ORDER_NUMBER_RE = re.compile(r"^SO-(\d+)$", re.IGNORECASE)

ALLOWED_STATUS_TRANSITIONS = {
    SalesOrder.Status.DRAFT: {
        SalesOrder.Status.DRAFT,
        SalesOrder.Status.CONFIRMED,
        SalesOrder.Status.CANCELLED,
    },
    SalesOrder.Status.CONFIRMED: {
        SalesOrder.Status.CONFIRMED,
        SalesOrder.Status.INVOICED,
        SalesOrder.Status.CANCELLED,
    },
    SalesOrder.Status.INVOICED: {
        SalesOrder.Status.INVOICED,
    },
    SalesOrder.Status.CANCELLED: {
        SalesOrder.Status.CANCELLED,
    },
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def next_sales_order_number(organization):
    numbers = SalesOrder.objects.filter(organization=organization).values_list(
        "sales_order_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = SALES_ORDER_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"SO-{highest + 1:06d}"


class SalesOrderLineSerializer(serializers.ModelSerializer):
    line_id = serializers.UUIDField(source="id", read_only=True)
    item_id = serializers.UUIDField(read_only=True, allow_null=True)
    quantity = serializers.SerializerMethodField()
    rate = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrderLine
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


class SalesOrderLineWriteSerializer(serializers.Serializer):
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


class SalesOrderSerializer(serializers.ModelSerializer):
    sales_order_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_name = serializers.SerializerMethodField()
    quote_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    tax_type_label = serializers.CharField(source="get_tax_type_display", read_only=True)
    order_date_label = serializers.SerializerMethodField()
    expected_shipment_date_label = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    line_items = SalesOrderLineSerializer(source="lines", many=True, read_only=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = (
            "sales_order_id",
            "organization_id",
            "customer_id",
            "customer_name",
            "quote_id",
            "sales_order_number",
            "reference_number",
            "order_date",
            "order_date_label",
            "expected_shipment_date",
            "expected_shipment_date_label",
            "payment_terms",
            "delivery_method",
            "salesperson_id",
            "salesperson_name",
            "project_id",
            "project_name",
            "subject",
            "tax_type",
            "tax_type_label",
            "customer_notes",
            "terms_and_conditions",
            "status",
            "status_label",
            "confirmed_at",
            "invoiced_at",
            "cancelled_at",
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

    def get_order_date_label(self, obj):
        if not obj.order_date:
            return ""
        return obj.order_date.strftime("%d %b %Y")

    def get_expected_shipment_date_label(self, obj):
        if not obj.expected_shipment_date:
            return ""
        return obj.expected_shipment_date.strftime("%d %b %Y")

    def get_total_amount(self, obj):
        return money(obj.total_amount)

    def get_currency(self, obj):
        if obj.currency:
            return obj.currency
        if obj.customer and getattr(obj.customer, "currency", None):
            return obj.customer.currency
        if obj.organization and obj.organization.currency:
            return obj.organization.currency
        return "INR"

    def get_attachments(self, obj):
        rows = Attachment.objects.filter(
            attachable_type="sales_order",
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


class SalesOrderWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    quote_id = serializers.UUIDField(required=False, allow_null=True)
    sales_order_number = serializers.CharField(required=False, allow_blank=True)
    order_date = serializers.DateField(required=False, allow_null=True)
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)
    line_items = SalesOrderLineWriteSerializer(many=True, required=False)
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = SalesOrder
        fields = (
            "organization_id",
            "customer_id",
            "quote_id",
            "sales_order_number",
            "reference_number",
            "order_date",
            "expected_shipment_date",
            "payment_terms",
            "delivery_method",
            "salesperson_id",
            "salesperson_name",
            "project_id",
            "project_name",
            "subject",
            "tax_type",
            "customer_notes",
            "terms_and_conditions",
            "status",
            "currency",
            "action",
            "line_items",
            "attachment_ids",
        )

    def validate_tax_type(self, value):
        if not value:
            return SalesOrder.TaxType.EXCLUSIVE
        key = str(value).strip().lower()
        aliases = {"exclusive": "exclusive", "inclusive": "inclusive"}
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid tax type. Allowed values: exclusive, inclusive."
            )
        return aliases[key]

    def validate_status(self, value):
        if not value:
            return SalesOrder.Status.DRAFT
        key = str(value).strip().lower()
        if key not in SalesOrder.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(SalesOrder.Status.values)}."
            )
        return key

    def validate_action(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save_as_draft": "save_as_draft",
            "draft": "save_as_draft",
            "save_and_confirm": "save_and_confirm",
            "save_as_confirmed": "save_and_confirm",
            "confirm": "save_and_confirm",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save_as_draft, save_as_confirmed."
            )
        return aliases[key]

    def validate_sales_order_number(self, value):
        return (value or "").strip().upper()

    def validate_payment_terms(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        key = key.replace("due_on_receipt", "due_on_receipt")
        label_key = str(value).strip().lower()
        if label_key in PAYMENT_TERM_ALIASES:
            return PAYMENT_TERM_ALIASES[label_key]
        if key in PAYMENT_TERM_ALIASES:
            return PAYMENT_TERM_ALIASES[key]
        allowed = {choice[0] for choice in PAYMENT_TERMS}
        if key in allowed:
            return key
        raise serializers.ValidationError(
            f"Invalid payment terms. Allowed values: {', '.join(choice[0] for choice in PAYMENT_TERMS)}."
        )

    def validate_delivery_method(self, value):
        return (value or "").strip()

    def validate_salesperson_name(self, value):
        return (value or "").strip()

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        action = attrs.pop("action", "") or ""
        if action == "save_as_draft":
            attrs["status"] = SalesOrder.Status.DRAFT
        elif action == "save_and_confirm":
            attrs["status"] = SalesOrder.Status.CONFIRMED

        quote_id = attrs.get("quote_id")
        if quote_id and not Quote.objects.filter(pk=quote_id).exists():
            raise serializers.ValidationError({"quote_id": "Quote not found."})

        customer_id = attrs.get("customer_id")
        if not self.partial and not customer_id and not self.instance and not quote_id:
            raise serializers.ValidationError(
                {"customer_id": "Customer is required."}
            )
        if customer_id and not Customer.objects.filter(pk=customer_id).exists():
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        if not attrs.get("order_date") and not self.partial and not self.instance:
            attrs["order_date"] = date.today()

        current_status = self.instance.status if self.instance else SalesOrder.Status.DRAFT
        next_status = attrs.get("status", current_status) or SalesOrder.Status.DRAFT
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
        needs_lines = next_status == SalesOrder.Status.CONFIRMED
        converting_from_quote = bool(quote_id) and not self.instance
        if needs_lines and lines is not None and not lines:
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before confirming a sales order."}
            )
        if needs_lines and lines is None and not self.instance and not converting_from_quote:
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before confirming a sales order."}
            )
        if (
            needs_lines
            and lines is None
            and self.instance
            and not self.instance.lines.exists()
        ):
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before confirming a sales order."}
            )
        return attrs

    def _replace_lines(self, sales_order, lines, organization):
        sales_order.lines.all().delete()
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
            SalesOrderLine.objects.create(
                sales_order=sales_order,
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
        sales_order.total_amount = total
        sales_order.save(update_fields=["total_amount", "updated_at"])

    def _copy_quote_lines(self, quote):
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
            for line in quote.lines.all()
        ]

    def _link_attachments(self, sales_order, attachment_ids, organization):
        if attachment_ids is None:
            return
        Attachment.objects.filter(
            attachable_type="sales_order",
            attachable_id=sales_order.id,
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
            attachment.attachable_type = "sales_order"
            attachment.attachable_id = sales_order.id
            attachment.save(update_fields=["attachable_type", "attachable_id", "updated_at"])

    def _apply_status_timestamps(self, data, instance=None):
        status_value = data.get("status")
        if status_value == SalesOrder.Status.CONFIRMED and not (
            instance and instance.confirmed_at
        ):
            data["confirmed_at"] = timezone.now()
        if status_value == SalesOrder.Status.INVOICED and not (
            instance and instance.invoiced_at
        ):
            data["invoiced_at"] = timezone.now()
        if status_value == SalesOrder.Status.CANCELLED and not (
            instance and instance.cancelled_at
        ):
            data["cancelled_at"] = timezone.now()
        return data

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        customer_id = validated_data.pop("customer_id", None)
        quote_id = validated_data.pop("quote_id", None)
        lines = validated_data.pop("line_items", None)
        attachment_ids = validated_data.pop("attachment_ids", None)

        quote = None
        if quote_id:
            quote = Quote.objects.filter(pk=quote_id, organization=organization).first()
            if not quote:
                raise serializers.ValidationError({"quote_id": "Quote not found."})
            if not customer_id:
                customer_id = quote.customer_id
            if not validated_data.get("reference_number"):
                validated_data["reference_number"] = quote.quote_number
            if not validated_data.get("subject"):
                validated_data["subject"] = quote.subject
            if not validated_data.get("tax_type"):
                validated_data["tax_type"] = quote.tax_type
            if not validated_data.get("customer_notes"):
                validated_data["customer_notes"] = quote.customer_notes
            if not validated_data.get("terms_and_conditions"):
                validated_data["terms_and_conditions"] = quote.terms_and_conditions
            if not validated_data.get("salesperson_id"):
                validated_data["salesperson_id"] = quote.salesperson_id
            if not validated_data.get("salesperson_name"):
                validated_data["salesperson_name"] = quote.salesperson_name
            if not validated_data.get("project_id"):
                validated_data["project_id"] = quote.project_id
            if not validated_data.get("project_name"):
                validated_data["project_name"] = quote.project_name
            if not validated_data.get("currency"):
                validated_data["currency"] = quote.currency
            if lines is None:
                lines = self._copy_quote_lines(quote)

        if validated_data.get("status") == SalesOrder.Status.CONFIRMED and not lines:
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before confirming a sales order."}
            )

        customer = Customer.objects.filter(pk=customer_id, organization=organization).first()
        if not customer:
            raise serializers.ValidationError({"customer_id": "Customer not found."})
        requested_number = (validated_data.get("sales_order_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and SalesOrder.objects.filter(
                organization=organization,
                sales_order_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["sales_order_number"] = next_sales_order_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = customer.currency or (
                organization.currency if organization else "INR"
            ) or "INR"
        if not validated_data.get("payment_terms"):
            validated_data["payment_terms"] = customer.payment_terms or ""
        validated_data = self._apply_status_timestamps(validated_data)
        sales_order = SalesOrder.objects.create(
            organization=organization,
            customer=customer,
            quote=quote,
            created_by=created_by,
            **validated_data,
        )
        self._replace_lines(sales_order, lines or [], organization)
        self._link_attachments(sales_order, attachment_ids, organization)
        if quote and quote.status != Quote.Status.CONVERTED:
            quote.status = Quote.Status.CONVERTED
            quote.save(update_fields=["status", "updated_at"])
        return sales_order

    def update(self, instance, validated_data):
        if instance.status in (SalesOrder.Status.INVOICED, SalesOrder.Status.CANCELLED):
            raise serializers.ValidationError(
                {"status": "Invoiced or cancelled sales orders cannot be updated."}
            )
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        customer_id = validated_data.pop("customer_id", None)
        quote_id = validated_data.pop("quote_id", None)
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
        if quote_id:
            quote = Quote.objects.filter(
                pk=quote_id,
                organization=instance.organization,
            ).first()
            if not quote:
                raise serializers.ValidationError({"quote_id": "Quote not found."})
            instance.quote = quote
        validated_data = self._apply_status_timestamps(validated_data, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if lines is not None:
            self._replace_lines(instance, lines, instance.organization)
        if attachment_ids is not None:
            self._link_attachments(instance, attachment_ids, instance.organization)
        return instance
