import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from apps.attachments.models import Attachment
from apps.customers.models import Customer
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.quotes.models import Quote, QuoteLine

ZERO = Decimal("0.00")
QUOTE_NUMBER_RE = re.compile(r"^QT-(\d+)$", re.IGNORECASE)


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def next_quote_number(organization):
    numbers = Quote.objects.filter(organization=organization).values_list(
        "quote_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = QUOTE_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"QT-{highest + 1:06d}"


class QuoteLineSerializer(serializers.ModelSerializer):
    line_id = serializers.UUIDField(source="id", read_only=True)
    item_id = serializers.UUIDField(read_only=True, allow_null=True)
    quantity = serializers.SerializerMethodField()
    rate = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = QuoteLine
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


class QuoteLineWriteSerializer(serializers.Serializer):
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


class QuoteSerializer(serializers.ModelSerializer):
    quote_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    tax_type_label = serializers.CharField(source="get_tax_type_display", read_only=True)
    quote_date_label = serializers.SerializerMethodField()
    expiry_date_label = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    line_items = QuoteLineSerializer(source="lines", many=True, read_only=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields = (
            "quote_id",
            "organization_id",
            "customer_id",
            "customer_name",
            "quote_number",
            "reference_number",
            "quote_date",
            "quote_date_label",
            "expiry_date",
            "expiry_date_label",
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
            "sent_at",
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

    def get_quote_date_label(self, obj):
        if not obj.quote_date:
            return ""
        return obj.quote_date.strftime("%d %b %Y")

    def get_expiry_date_label(self, obj):
        if not obj.expiry_date:
            return ""
        return obj.expiry_date.strftime("%d %b %Y")

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
            attachable_type="quote",
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


class QuoteWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    quote_number = serializers.CharField(required=False, allow_blank=True)
    quote_date = serializers.DateField(required=False, allow_null=True)
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)
    line_items = QuoteLineWriteSerializer(many=True, required=False)
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Quote
        fields = (
            "organization_id",
            "customer_id",
            "quote_number",
            "reference_number",
            "quote_date",
            "expiry_date",
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
            return Quote.TaxType.EXCLUSIVE
        key = str(value).strip().lower()
        aliases = {"exclusive": "exclusive", "inclusive": "inclusive"}
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid tax type. Allowed values: exclusive, inclusive."
            )
        return aliases[key]

    def validate_status(self, value):
        if not value:
            return Quote.Status.DRAFT
        key = str(value).strip().lower()
        if key not in Quote.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(Quote.Status.values)}."
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
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save_as_draft, save_and_send."
            )
        return aliases[key]

    def validate_quote_number(self, value):
        return (value or "").strip().upper()

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        action = attrs.pop("action", "") or ""
        if action == "save_as_draft":
            attrs["status"] = Quote.Status.DRAFT
        elif action == "save_and_send":
            attrs["status"] = Quote.Status.SENT

        customer_id = attrs.get("customer_id")
        if not self.partial and not customer_id and not self.instance:
            raise serializers.ValidationError(
                {"customer_id": "Customer is required."}
            )
        if customer_id and not Customer.objects.filter(pk=customer_id).exists():
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        if not attrs.get("quote_date") and not self.partial and not self.instance:
            attrs["quote_date"] = date.today()

        status_value = attrs.get("status")
        if status_value is None and self.instance:
            status_value = self.instance.status
        status_value = status_value or Quote.Status.DRAFT
        lines = attrs.get("line_items")
        if status_value == Quote.Status.SENT and lines is not None and not lines:
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before sending a quote."}
            )
        if status_value == Quote.Status.SENT and lines is None and not self.instance:
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before sending a quote."}
            )
        return attrs

    def _replace_lines(self, quote, lines, organization):
        quote.lines.all().delete()
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
            QuoteLine.objects.create(
                quote=quote,
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
        quote.total_amount = total
        quote.save(update_fields=["total_amount", "updated_at"])

    def _link_attachments(self, quote, attachment_ids, organization):
        if attachment_ids is None:
            return
        Attachment.objects.filter(
            attachable_type="quote",
            attachable_id=quote.id,
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
            attachment.attachable_type = "quote"
            attachment.attachable_id = quote.id
            attachment.save(update_fields=["attachable_type", "attachable_id", "updated_at"])

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        customer_id = validated_data.pop("customer_id", None)
        lines = validated_data.pop("line_items", [])
        attachment_ids = validated_data.pop("attachment_ids", None)
        customer = Customer.objects.filter(pk=customer_id, organization=organization).first()
        if not customer:
            raise serializers.ValidationError({"customer_id": "Customer not found."})
        if not validated_data.get("quote_number"):
            validated_data["quote_number"] = next_quote_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = customer.currency or (
                organization.currency if organization else "INR"
            ) or "INR"
        if validated_data.get("status") == Quote.Status.SENT:
            from django.utils import timezone

            validated_data["sent_at"] = timezone.now()
        quote = Quote.objects.create(
            organization=organization,
            customer=customer,
            created_by=created_by,
            **validated_data,
        )
        self._replace_lines(quote, lines, organization)
        self._link_attachments(quote, attachment_ids, organization)
        return quote

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        customer_id = validated_data.pop("customer_id", None)
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
        if validated_data.get("status") == Quote.Status.SENT and not instance.sent_at:
            from django.utils import timezone

            instance.sent_at = timezone.now()
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if lines is not None:
            self._replace_lines(instance, lines, instance.organization)
        if attachment_ids is not None:
            self._link_attachments(instance, attachment_ids, instance.organization)
        return instance
