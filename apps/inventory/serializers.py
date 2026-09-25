from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.attachments.models import Attachment
from apps.inventory.models import (
    InventoryAdjustment,
    InventoryAdjustmentActivity,
    InventoryAdjustmentLine,
)
from apps.inventory.services import (
    ATTACHABLE_TYPE,
    apply_stock,
    display_name_for_user,
    refresh_totals,
)
from apps.items.models import Item
from apps.organizations.models import Organization

ZERO = Decimal("0.00")


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def quantity_text(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount == amount.to_integral_value():
        whole = int(amount)
        return f"{whole:+d}" if whole != 0 else "0"
    formatted = f"{amount:.2f}"
    if amount > 0:
        return f"+{formatted}"
    return formatted


class InventoryAdjustmentLineSerializer(serializers.ModelSerializer):
    line_id = serializers.UUIDField(source="id", read_only=True)
    item_id = serializers.UUIDField(read_only=True, allow_null=True)
    item_name = serializers.SerializerMethodField()
    sku = serializers.SerializerMethodField()
    quantity_adjusted = serializers.SerializerMethodField()
    rate = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    class Meta:
        model = InventoryAdjustmentLine
        fields = (
            "line_id",
            "item_id",
            "item_name",
            "sku",
            "quantity_adjusted",
            "rate",
            "value",
        )
        read_only_fields = fields

    def get_item_name(self, obj):
        return obj.item.name if obj.item else None

    def get_sku(self, obj):
        return obj.item.sku if obj.item else None

    def get_quantity_adjusted(self, obj):
        return money(obj.quantity_adjusted)

    def get_rate(self, obj):
        return money(obj.rate)

    def get_value(self, obj):
        return money(obj.value)


class InventoryAdjustmentLineWriteSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity_adjusted = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    rate = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    value = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )


class InventoryAdjustmentSerializer(serializers.ModelSerializer):
    adjustment_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    date_label = serializers.SerializerMethodField()
    quantity_change = serializers.SerializerMethodField()
    quantity_change_label = serializers.SerializerMethodField()
    adjustment_value = serializers.SerializerMethodField()
    direction = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    attachments_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    lines = InventoryAdjustmentLineSerializer(many=True, read_only=True)

    class Meta:
        model = InventoryAdjustment
        fields = (
            "adjustment_id",
            "organization_id",
            "adjustment_type",
            "reason",
            "date",
            "date_label",
            "status",
            "status_label",
            "reference_number",
            "description",
            "account",
            "adjusted_by_name",
            "quantity_change",
            "quantity_change_label",
            "adjustment_value",
            "direction",
            "currency",
            "stock_applied",
            "attachments_count",
            "comments_count",
            "lines",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_date_label(self, obj):
        if not obj.date:
            return ""
        return obj.date.strftime("%d %b %Y")

    def get_quantity_change(self, obj):
        return money(obj.quantity_change)

    def get_quantity_change_label(self, obj):
        return quantity_text(obj.quantity_change)

    def get_adjustment_value(self, obj):
        return money(obj.adjustment_value)

    def get_direction(self, obj):
        if obj.adjustment_type == InventoryAdjustment.AdjustmentType.VALUE:
            amount = obj.adjustment_value or ZERO
        else:
            amount = obj.quantity_change or ZERO
        if amount > 0:
            return "increase"
        if amount < 0:
            return "decrease"
        return "none"

    def get_currency(self, obj):
        if obj.organization and obj.organization.currency:
            return obj.organization.currency
        return "INR"

    def get_attachments_count(self, obj):
        annotated = getattr(obj, "attachments_total", None)
        if annotated is not None:
            return annotated
        return Attachment.objects.filter(
            organization_id=obj.organization_id,
            attachable_type=ATTACHABLE_TYPE,
            attachable_id=obj.id,
        ).count()

    def get_comments_count(self, obj):
        annotated = getattr(obj, "comments_total", None)
        if annotated is not None:
            return annotated
        return obj.activities.filter(
            activity_type=InventoryAdjustmentActivity.ActivityType.COMMENT
        ).count()


class InventoryAdjustmentActivitySerializer(serializers.ModelSerializer):
    activity_id = serializers.UUIDField(source="id", read_only=True)
    adjustment_id = serializers.UUIDField(read_only=True)
    activity_type_label = serializers.CharField(
        source="get_activity_type_display",
        read_only=True,
    )
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()
    created_at_label = serializers.SerializerMethodField()

    class Meta:
        model = InventoryAdjustmentActivity
        fields = (
            "activity_id",
            "adjustment_id",
            "activity_type",
            "activity_type_label",
            "message",
            "created_by",
            "created_by_name",
            "created_at",
            "created_at_label",
        )
        read_only_fields = fields

    def get_created_by_name(self, obj):
        return display_name_for_user(obj.created_by)

    def get_created_at_label(self, obj):
        if not obj.created_at:
            return ""
        return timezone.localtime(obj.created_at).strftime("%d %b %Y %I:%M %p")


class InventoryAdjustmentWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    lines = InventoryAdjustmentLineWriteSerializer(many=True, required=False)

    class Meta:
        model = InventoryAdjustment
        fields = (
            "organization_id",
            "adjustment_type",
            "reason",
            "date",
            "status",
            "reference_number",
            "description",
            "account",
            "adjusted_by_name",
            "lines",
        )

    def validate_reason(self, value):
        reason = (value or "").strip()
        if not reason:
            raise serializers.ValidationError("Reason is required.")
        return reason

    def validate_adjustment_type(self, value):
        if value and value not in InventoryAdjustment.AdjustmentType.values:
            raise serializers.ValidationError(
                f"Invalid adjustment_type. Allowed values: {', '.join(InventoryAdjustment.AdjustmentType.values)}."
            )
        return value

    def validate_status(self, value):
        if value and value not in InventoryAdjustment.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(InventoryAdjustment.Status.values)}."
            )
        return value

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.status == InventoryAdjustment.Status.COMPLETED:
            raise serializers.ValidationError(
                "Completed adjustments cannot be edited."
            )

        adjustment_type = attrs.get("adjustment_type")
        if adjustment_type is None and instance:
            adjustment_type = instance.adjustment_type
        adjustment_type = adjustment_type or InventoryAdjustment.AdjustmentType.QUANTITY

        lines = attrs.get("lines")
        if lines is None and not self.partial:
            lines = []
            attrs["lines"] = lines
        if lines is not None:
            if not lines:
                raise serializers.ValidationError(
                    {"lines": "At least one adjustment line is required."}
                )
            for index, line in enumerate(lines):
                item_id = line.get("item_id")
                if not Item.objects.filter(pk=item_id).exists():
                    raise serializers.ValidationError(
                        {"lines": {index: {"item_id": "Item not found."}}}
                    )
                quantity = line.get("quantity_adjusted")
                value = line.get("value")
                rate = line.get("rate")
                if adjustment_type == InventoryAdjustment.AdjustmentType.QUANTITY:
                    if quantity is None:
                        raise serializers.ValidationError(
                            {
                                "lines": {
                                    index: {
                                        "quantity_adjusted": "Quantity is required for quantity adjustments."
                                    }
                                }
                            }
                        )
                elif value is None and quantity is None:
                    raise serializers.ValidationError(
                        {
                            "lines": {
                                index: {
                                    "value": "Value is required for value adjustments."
                                }
                            }
                        }
                    )
                if rate is None:
                    line["rate"] = ZERO
        return attrs

    def _replace_lines(self, adjustment, lines, organization):
        adjustment.lines.all().delete()
        for line in lines:
            item = Item.objects.filter(
                pk=line["item_id"],
                organization=organization,
            ).first()
            if not item:
                raise serializers.ValidationError(
                    {"lines": "Item not found in this organization."}
                )
            quantity = line.get("quantity_adjusted")
            if quantity is None:
                quantity = ZERO
            rate = line.get("rate")
            if rate is None:
                rate = item.cost_price or item.rate_per_unit or ZERO
            value = line.get("value")
            if value is None:
                value = quantity * rate
            InventoryAdjustmentLine.objects.create(
                adjustment=adjustment,
                item=item,
                quantity_adjusted=quantity,
                rate=rate,
                value=value,
            )
        refresh_totals(adjustment)

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        lines = validated_data.pop("lines", [])
        if not validated_data.get("adjusted_by_name"):
            validated_data["adjusted_by_name"] = display_name_for_user(
                created_by,
                organization,
            )
        if not validated_data.get("account"):
            validated_data["account"] = "Inventory Asset"
        adjustment = InventoryAdjustment.objects.create(
            organization=organization,
            created_by=created_by,
            **validated_data,
        )
        self._replace_lines(adjustment, lines, organization)
        if adjustment.status == InventoryAdjustment.Status.COMPLETED:
            apply_stock(adjustment)
        return adjustment

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        lines = validated_data.pop("lines", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if lines is not None:
            self._replace_lines(instance, lines, instance.organization)
        else:
            refresh_totals(instance)
        if instance.status == InventoryAdjustment.Status.COMPLETED:
            apply_stock(instance)
        return instance
