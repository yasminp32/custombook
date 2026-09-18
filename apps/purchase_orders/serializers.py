import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.organizations.models import Organization
from apps.purchase_orders.models import PurchaseOrder
from apps.vendors.models import Vendor

ZERO = Decimal("0.00")
PURCHASE_ORDER_NUMBER_RE = re.compile(r"^PO-(\d+)$", re.IGNORECASE)

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "AED": "AED",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

ALLOWED_STATUS_TRANSITIONS = {
    PurchaseOrder.Status.DRAFT: {
        PurchaseOrder.Status.DRAFT,
        PurchaseOrder.Status.ISSUED,
        PurchaseOrder.Status.CANCELLED,
    },
    PurchaseOrder.Status.ISSUED: {
        PurchaseOrder.Status.ISSUED,
        PurchaseOrder.Status.BILLED,
        PurchaseOrder.Status.CANCELLED,
    },
    PurchaseOrder.Status.BILLED: {
        PurchaseOrder.Status.BILLED,
    },
    PurchaseOrder.Status.CANCELLED: {
        PurchaseOrder.Status.CANCELLED,
    },
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def currency_symbol(code):
    return CURRENCY_SYMBOLS.get((code or "INR").upper(), code or "INR")


def next_purchase_order_number(organization):
    numbers = PurchaseOrder.objects.filter(organization=organization).values_list(
        "purchase_order_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = PURCHASE_ORDER_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"PO-{highest + 1:05d}"


class PurchaseOrderSerializer(serializers.ModelSerializer):
    purchase_order_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    order_date_label = serializers.SerializerMethodField()
    expected_delivery_date_label = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = (
            "purchase_order_id",
            "organization_id",
            "vendor_id",
            "vendor_name",
            "purchase_order_number",
            "reference_number",
            "order_date",
            "order_date_label",
            "expected_delivery_date",
            "expected_delivery_date_label",
            "amount",
            "currency",
            "currency_symbol",
            "status",
            "status_label",
            "issued_at",
            "billed_at",
            "cancelled_at",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_vendor_name(self, obj):
        if not obj.vendor:
            return ""
        return obj.vendor.display_name or obj.vendor.company_name or ""

    def get_order_date_label(self, obj):
        if not obj.order_date:
            return ""
        return obj.order_date.strftime("%d %b %Y")

    def get_expected_delivery_date_label(self, obj):
        if not obj.expected_delivery_date:
            return ""
        return obj.expected_delivery_date.strftime("%d %b %Y")

    def get_amount(self, obj):
        return money(obj.amount)

    def get_currency_symbol(self, obj):
        return currency_symbol(obj.currency)


class PurchaseOrderWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    vendor_id = serializers.UUIDField(required=False, allow_null=True)
    purchase_order_number = serializers.CharField(required=False, allow_blank=True)
    order_date = serializers.DateField(required=False, allow_null=True)
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    amount = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = PurchaseOrder
        fields = (
            "organization_id",
            "vendor_id",
            "purchase_order_number",
            "reference_number",
            "order_date",
            "expected_delivery_date",
            "amount",
            "currency",
            "status",
            "action",
        )

    def validate_purchase_order_number(self, value):
        return (value or "").strip().upper()

    def validate_reference_number(self, value):
        return (value or "").strip()

    def validate_status(self, value):
        if not value:
            return PurchaseOrder.Status.DRAFT
        key = str(value).strip().lower()
        if key not in PurchaseOrder.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(PurchaseOrder.Status.values)}."
            )
        return key

    def validate_action(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save": "save_as_draft",
            "save_as_draft": "save_as_draft",
            "draft": "save_as_draft",
            "save_as_issued": "save_as_issued",
            "issued": "save_as_issued",
            "mark_as_billed": "mark_as_billed",
            "billed": "mark_as_billed",
            "cancel": "cancel",
            "cancelled": "cancel",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save_as_draft, save_as_issued, mark_as_billed, cancel."
            )
        return aliases[key]

    def validate_amount(self, value):
        if value is None:
            return ZERO
        amount = Decimal(value)
        if amount < ZERO:
            raise serializers.ValidationError("Amount cannot be negative.")
        return amount

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        action = attrs.pop("action", "") or ""
        if action == "save_as_draft":
            attrs["status"] = PurchaseOrder.Status.DRAFT
        elif action == "save_as_issued":
            attrs["status"] = PurchaseOrder.Status.ISSUED
        elif action == "mark_as_billed":
            attrs["status"] = PurchaseOrder.Status.BILLED
        elif action == "cancel":
            attrs["status"] = PurchaseOrder.Status.CANCELLED

        vendor_id = attrs.get("vendor_id")
        if not self.partial and not vendor_id and not self.instance:
            raise serializers.ValidationError({"vendor_id": "Vendor is required."})
        if vendor_id and not Vendor.objects.filter(pk=vendor_id).exists():
            raise serializers.ValidationError({"vendor_id": "Vendor not found."})

        if not attrs.get("order_date") and not self.partial and not self.instance:
            attrs["order_date"] = date.today()

        if attrs.get("amount") is None and not self.partial and not self.instance:
            attrs["amount"] = ZERO

        current_status = self.instance.status if self.instance else PurchaseOrder.Status.DRAFT
        next_status = attrs.get("status", current_status) or PurchaseOrder.Status.DRAFT
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if next_status not in allowed:
            raise serializers.ValidationError(
                {
                    "status": (
                        f"Cannot change status from {current_status} to {next_status}."
                    )
                }
            )
        return attrs

    def _apply_status_timestamps(self, data, instance=None):
        status_value = data.get("status")
        if status_value == PurchaseOrder.Status.ISSUED and not (instance and instance.issued_at):
            data["issued_at"] = timezone.now()
        if status_value == PurchaseOrder.Status.BILLED and not (instance and instance.billed_at):
            data["billed_at"] = timezone.now()
        if status_value == PurchaseOrder.Status.CANCELLED and not (
            instance and instance.cancelled_at
        ):
            data["cancelled_at"] = timezone.now()
        return data

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        vendor_id = validated_data.pop("vendor_id", None)
        vendor = Vendor.objects.filter(pk=vendor_id, organization=organization).first()
        if not vendor:
            raise serializers.ValidationError({"vendor_id": "Vendor not found."})
        requested_number = (validated_data.get("purchase_order_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and PurchaseOrder.objects.filter(
                organization=organization,
                purchase_order_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["purchase_order_number"] = next_purchase_order_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = (
                organization.currency if organization else "INR"
            ) or "INR"
        if not validated_data.get("status"):
            validated_data["status"] = PurchaseOrder.Status.DRAFT
        validated_data = self._apply_status_timestamps(validated_data)
        return PurchaseOrder.objects.create(
            organization=organization,
            vendor=vendor,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        if instance.status in (PurchaseOrder.Status.BILLED, PurchaseOrder.Status.CANCELLED):
            raise serializers.ValidationError(
                {"status": "Billed or cancelled purchase orders cannot be updated."}
            )
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        vendor_id = validated_data.pop("vendor_id", None)
        if vendor_id:
            vendor = Vendor.objects.filter(
                pk=vendor_id,
                organization=instance.organization,
            ).first()
            if not vendor:
                raise serializers.ValidationError({"vendor_id": "Vendor not found."})
            instance.vendor = vendor
        requested_number = validated_data.get("purchase_order_number")
        if requested_number:
            taken = (
                PurchaseOrder.objects.filter(
                    organization=instance.organization,
                    purchase_order_number=requested_number,
                )
                .exclude(pk=instance.pk)
                .exists()
            )
            if taken:
                raise serializers.ValidationError(
                    {"purchase_order_number": "Purchase order number already exists."}
                )
        validated_data = self._apply_status_timestamps(validated_data, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
