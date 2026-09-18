import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.attachments.models import Attachment
from apps.customers.models import Customer
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.delivery_challans.models import DeliveryChallan, DeliveryChallanLine
from apps.sales_orders.models import SalesOrder

ZERO = Decimal("0.00")
CHALLAN_NUMBER_RE = re.compile(r"^DC-(\d+)$", re.IGNORECASE)

CHALLAN_TYPE_ALIASES = {
    "job_work": "job_work",
    "job work": "job_work",
    "jobwork": "job_work",
    "supply_on_approval": "supply_on_approval",
    "supply on approval": "supply_on_approval",
    "supply_of_liquid_gas": "supply_of_liquid_gas",
    "supply of liquid gas": "supply_of_liquid_gas",
    "others": "others",
    "other": "others",
}

ALLOWED_STATUS_TRANSITIONS = {
    DeliveryChallan.Status.DRAFT: {
        DeliveryChallan.Status.DRAFT,
        DeliveryChallan.Status.DELIVERED,
        DeliveryChallan.Status.CANCELLED,
    },
    DeliveryChallan.Status.DELIVERED: {
        DeliveryChallan.Status.DELIVERED,
        DeliveryChallan.Status.RETURNED,
        DeliveryChallan.Status.CANCELLED,
    },
    DeliveryChallan.Status.RETURNED: {
        DeliveryChallan.Status.RETURNED,
    },
    DeliveryChallan.Status.CANCELLED: {
        DeliveryChallan.Status.CANCELLED,
    },
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def next_challan_number(organization):
    numbers = DeliveryChallan.objects.filter(organization=organization).values_list(
        "challan_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = CHALLAN_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"DC-{highest + 1:05d}"


class DeliveryChallanLineSerializer(serializers.ModelSerializer):
    line_id = serializers.UUIDField(source="id", read_only=True)
    item_id = serializers.UUIDField(read_only=True, allow_null=True)
    quantity = serializers.SerializerMethodField()
    rate = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryChallanLine
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


class DeliveryChallanLineWriteSerializer(serializers.Serializer):
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


class DeliveryChallanSerializer(serializers.ModelSerializer):
    delivery_challan_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_name = serializers.SerializerMethodField()
    sales_order_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    challan_type_label = serializers.CharField(source="get_challan_type_display", read_only=True)
    tax_type_label = serializers.CharField(source="get_tax_type_display", read_only=True)
    challan_date_label = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    line_items = DeliveryChallanLineSerializer(source="lines", many=True, read_only=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryChallan
        fields = (
            "delivery_challan_id",
            "organization_id",
            "customer_id",
            "customer_name",
            "sales_order_id",
            "challan_number",
            "reference_number",
            "challan_date",
            "challan_date_label",
            "challan_type",
            "challan_type_label",
            "tax_type",
            "tax_type_label",
            "customer_notes",
            "terms_and_conditions",
            "status",
            "status_label",
            "delivered_at",
            "returned_at",
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

    def get_challan_date_label(self, obj):
        if not obj.challan_date:
            return ""
        return obj.challan_date.strftime("%d %b %Y")

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
            attachable_type="delivery_challan",
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


class DeliveryChallanWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    sales_order_id = serializers.UUIDField(required=False, allow_null=True)
    challan_number = serializers.CharField(required=False, allow_blank=True)
    challan_date = serializers.DateField(required=False, allow_null=True)
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)
    line_items = DeliveryChallanLineWriteSerializer(many=True, required=False)
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = DeliveryChallan
        fields = (
            "organization_id",
            "customer_id",
            "sales_order_id",
            "challan_number",
            "reference_number",
            "challan_date",
            "challan_type",
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
            return DeliveryChallan.TaxType.EXCLUSIVE
        key = str(value).strip().lower()
        aliases = {"exclusive": "exclusive", "inclusive": "inclusive"}
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid tax type. Allowed values: exclusive, inclusive."
            )
        return aliases[key]

    def validate_challan_type(self, value):
        if not value:
            return DeliveryChallan.ChallanType.JOB_WORK
        key = str(value).strip().lower()
        if key not in CHALLAN_TYPE_ALIASES:
            raise serializers.ValidationError(
                "Invalid type. Allowed values: job_work, supply_on_approval, "
                "supply_of_liquid_gas, others."
            )
        return CHALLAN_TYPE_ALIASES[key]

    def validate_status(self, value):
        if not value:
            return DeliveryChallan.Status.DRAFT
        key = str(value).strip().lower()
        if key not in DeliveryChallan.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(DeliveryChallan.Status.values)}."
            )
        return key

    def validate_action(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save_as_draft": "save_as_draft",
            "draft": "save_as_draft",
            "save_as_delivered": "save_as_delivered",
            "deliver": "save_as_delivered",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save_as_draft, save_as_delivered."
            )
        return aliases[key]

    def validate_challan_number(self, value):
        return (value or "").strip().upper()

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        action = attrs.pop("action", "") or ""
        if action == "save_as_draft":
            attrs["status"] = DeliveryChallan.Status.DRAFT
        elif action == "save_as_delivered":
            attrs["status"] = DeliveryChallan.Status.DELIVERED

        customer_id = attrs.get("customer_id")
        if not self.partial and not customer_id and not self.instance:
            raise serializers.ValidationError({"customer_id": "Customer is required."})
        if customer_id and not Customer.objects.filter(pk=customer_id).exists():
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        sales_order_id = attrs.get("sales_order_id")
        if sales_order_id and not SalesOrder.objects.filter(pk=sales_order_id).exists():
            raise serializers.ValidationError({"sales_order_id": "Sales order not found."})

        if not attrs.get("challan_date") and not self.partial and not self.instance:
            attrs["challan_date"] = date.today()

        current_status = self.instance.status if self.instance else DeliveryChallan.Status.DRAFT
        next_status = attrs.get("status", current_status) or DeliveryChallan.Status.DRAFT
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
        needs_lines = next_status == DeliveryChallan.Status.DELIVERED
        if needs_lines and lines is not None and not lines:
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before marking as delivered."}
            )
        if needs_lines and lines is None and not self.instance:
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before marking as delivered."}
            )
        if (
            needs_lines
            and lines is None
            and self.instance
            and not self.instance.lines.exists()
        ):
            raise serializers.ValidationError(
                {"line_items": "Add at least one line item before marking as delivered."}
            )
        return attrs

    def _replace_lines(self, challan, lines, organization):
        challan.lines.all().delete()
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
            DeliveryChallanLine.objects.create(
                delivery_challan=challan,
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
        challan.total_amount = total
        challan.save(update_fields=["total_amount", "updated_at"])

    def _link_attachments(self, challan, attachment_ids, organization):
        if attachment_ids is None:
            return
        Attachment.objects.filter(
            attachable_type="delivery_challan",
            attachable_id=challan.id,
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
            attachment.attachable_type = "delivery_challan"
            attachment.attachable_id = challan.id
            attachment.save(update_fields=["attachable_type", "attachable_id", "updated_at"])

    def _apply_status_timestamps(self, data, instance=None):
        status_value = data.get("status")
        if status_value == DeliveryChallan.Status.DELIVERED and not (
            instance and instance.delivered_at
        ):
            data["delivered_at"] = timezone.now()
        if status_value == DeliveryChallan.Status.RETURNED and not (
            instance and instance.returned_at
        ):
            data["returned_at"] = timezone.now()
        if status_value == DeliveryChallan.Status.CANCELLED and not (
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
                lines = [
                    {
                        "item_id": line.item_id,
                        "name": line.name,
                        "description": line.description,
                        "quantity": line.quantity,
                        "rate": line.rate,
                        "tax": line.tax,
                        "sort_order": line.sort_order,
                    }
                    for line in sales_order.lines.all()
                ]

        requested_number = (validated_data.get("challan_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and DeliveryChallan.objects.filter(
                organization=organization,
                challan_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["challan_number"] = next_challan_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = customer.currency or (
                organization.currency if organization else "INR"
            ) or "INR"
        validated_data = self._apply_status_timestamps(validated_data)
        challan = DeliveryChallan.objects.create(
            organization=organization,
            customer=customer,
            sales_order=sales_order,
            created_by=created_by,
            **validated_data,
        )
        self._replace_lines(challan, lines or [], organization)
        self._link_attachments(challan, attachment_ids, organization)
        return challan

    def update(self, instance, validated_data):
        if instance.status in (
            DeliveryChallan.Status.RETURNED,
            DeliveryChallan.Status.CANCELLED,
        ):
            raise serializers.ValidationError(
                {"status": "Returned or cancelled delivery challans cannot be updated."}
            )
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        customer_id = validated_data.pop("customer_id", None)
        sales_order_id = validated_data.pop("sales_order_id", None)
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
        validated_data = self._apply_status_timestamps(validated_data, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if lines is not None:
            self._replace_lines(instance, lines, instance.organization)
        if attachment_ids is not None:
            self._link_attachments(instance, attachment_ids, instance.organization)
        return instance
