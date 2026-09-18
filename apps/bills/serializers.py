import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.bills.models import DEFAULT_DUE_DAYS, Bill
from apps.organizations.models import Organization
from apps.purchase_orders.models import PurchaseOrder
from apps.vendors.models import Vendor

ZERO = Decimal("0.00")
BILL_NUMBER_RE = re.compile(r"^BILL-(\d+)$", re.IGNORECASE)

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "AED": "AED",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

ALLOWED_STATUS_TRANSITIONS = {
    Bill.Status.DRAFT: {
        Bill.Status.DRAFT,
        Bill.Status.OPEN,
    },
    Bill.Status.OPEN: {
        Bill.Status.OPEN,
        Bill.Status.PAID,
        Bill.Status.PARTIALLY_PAID,
    },
    Bill.Status.PARTIALLY_PAID: {
        Bill.Status.PARTIALLY_PAID,
        Bill.Status.PAID,
    },
    Bill.Status.PAID: {
        Bill.Status.PAID,
    },
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def currency_symbol(code):
    return CURRENCY_SYMBOLS.get((code or "INR").upper(), code or "INR")


def next_bill_number(organization):
    numbers = Bill.objects.filter(organization=organization).values_list(
        "bill_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = BILL_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"BILL-{highest + 1:05d}"


def default_due_date(bill_date):
    bill_date = bill_date or date.today()
    return bill_date + timedelta(days=DEFAULT_DUE_DAYS)


class BillSerializer(serializers.ModelSerializer):
    bill_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_name = serializers.SerializerMethodField()
    purchase_order_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    stored_status = serializers.CharField(source="status", read_only=True)
    bill_date_label = serializers.SerializerMethodField()
    due_date_label = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = (
            "bill_id",
            "organization_id",
            "vendor_id",
            "vendor_name",
            "purchase_order_id",
            "bill_number",
            "bill_date",
            "bill_date_label",
            "due_date",
            "due_date_label",
            "amount",
            "amount_paid",
            "currency",
            "currency_symbol",
            "status",
            "stored_status",
            "status_label",
            "is_overdue",
            "opened_at",
            "paid_at",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_vendor_name(self, obj):
        if not obj.vendor:
            return ""
        return obj.vendor.display_name or obj.vendor.company_name or ""

    def get_status(self, obj):
        return obj.effective_status()

    def get_status_label(self, obj):
        return obj.display_status_label()

    def get_bill_date_label(self, obj):
        if not obj.bill_date:
            return ""
        return obj.bill_date.strftime("%d %b %Y")

    def get_due_date_label(self, obj):
        if not obj.due_date:
            return ""
        return f"Due {obj.due_date.strftime('%d %b %Y')}"

    def get_amount(self, obj):
        return money(obj.amount)

    def get_amount_paid(self, obj):
        return money(obj.amount_paid)

    def get_currency_symbol(self, obj):
        return currency_symbol(obj.currency)

    def get_is_overdue(self, obj):
        return obj.is_overdue()


class BillWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    vendor_id = serializers.UUIDField(required=False, allow_null=True)
    purchase_order_id = serializers.UUIDField(required=False, allow_null=True)
    bill_number = serializers.CharField(required=False, allow_blank=True)
    bill_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    amount = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    amount_paid = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Bill
        fields = (
            "organization_id",
            "vendor_id",
            "purchase_order_id",
            "bill_number",
            "bill_date",
            "due_date",
            "amount",
            "amount_paid",
            "currency",
            "status",
            "action",
        )

    def validate_bill_number(self, value):
        return (value or "").strip().upper()

    def validate_status(self, value):
        if not value:
            return Bill.Status.DRAFT
        key = str(value).strip().lower().replace(" ", "_")
        if key == "overdue":
            return Bill.Status.OPEN
        if key not in Bill.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(Bill.Status.values)}."
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
            "save_as_open": "save_as_open",
            "open": "save_as_open",
            "mark_as_paid": "mark_as_paid",
            "paid": "mark_as_paid",
            "mark_as_partially_paid": "mark_as_partially_paid",
            "partially_paid": "mark_as_partially_paid",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save_as_draft, save_as_open, mark_as_paid, mark_as_partially_paid."
            )
        return aliases[key]

    def validate_amount(self, value):
        if value is None:
            return ZERO
        amount = Decimal(value)
        if amount < ZERO:
            raise serializers.ValidationError("Amount cannot be negative.")
        return amount

    def validate_amount_paid(self, value):
        if value is None:
            return ZERO
        amount = Decimal(value)
        if amount < ZERO:
            raise serializers.ValidationError("Amount paid cannot be negative.")
        return amount

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        action = attrs.pop("action", "") or ""
        if action == "save_as_draft":
            attrs["status"] = Bill.Status.DRAFT
        elif action == "save_as_open":
            attrs["status"] = Bill.Status.OPEN
        elif action == "mark_as_paid":
            attrs["status"] = Bill.Status.PAID
        elif action == "mark_as_partially_paid":
            attrs["status"] = Bill.Status.PARTIALLY_PAID

        vendor_id = attrs.get("vendor_id")
        if not self.partial and not vendor_id and not self.instance:
            raise serializers.ValidationError({"vendor_id": "Vendor is required."})
        if vendor_id and not Vendor.objects.filter(pk=vendor_id).exists():
            raise serializers.ValidationError({"vendor_id": "Vendor not found."})

        if not attrs.get("bill_date") and not self.partial and not self.instance:
            attrs["bill_date"] = date.today()

        bill_date = attrs.get("bill_date")
        if bill_date is None and self.instance:
            bill_date = self.instance.bill_date
        if not attrs.get("due_date") and not self.partial and not self.instance:
            attrs["due_date"] = default_due_date(bill_date)

        if attrs.get("amount") is None and not self.partial and not self.instance:
            attrs["amount"] = ZERO

        current_status = self.instance.status if self.instance else Bill.Status.DRAFT
        next_status = attrs.get("status", current_status) or Bill.Status.DRAFT
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
        if status_value == Bill.Status.OPEN and not (instance and instance.opened_at):
            data["opened_at"] = timezone.now()
        if status_value == Bill.Status.PAID:
            if not (instance and instance.paid_at):
                data["paid_at"] = timezone.now()
            amount = data.get("amount")
            if amount is None and instance:
                amount = instance.amount
            if amount is not None and data.get("amount_paid") is None:
                data["amount_paid"] = amount
        return data

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        vendor_id = validated_data.pop("vendor_id", None)
        purchase_order_id = validated_data.pop("purchase_order_id", None)
        vendor = Vendor.objects.filter(pk=vendor_id, organization=organization).first()
        if not vendor:
            raise serializers.ValidationError({"vendor_id": "Vendor not found."})
        purchase_order = None
        if purchase_order_id:
            purchase_order = PurchaseOrder.objects.filter(
                pk=purchase_order_id,
                organization=organization,
            ).first()
            if not purchase_order:
                raise serializers.ValidationError(
                    {"purchase_order_id": "Purchase order not found."}
                )
        requested_number = (validated_data.get("bill_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and Bill.objects.filter(
                organization=organization,
                bill_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["bill_number"] = next_bill_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = (
                organization.currency if organization else "INR"
            ) or "INR"
        if not validated_data.get("status"):
            validated_data["status"] = Bill.Status.DRAFT
        if not validated_data.get("due_date"):
            validated_data["due_date"] = default_due_date(validated_data.get("bill_date"))
        validated_data = self._apply_status_timestamps(validated_data)
        return Bill.objects.create(
            organization=organization,
            vendor=vendor,
            purchase_order=purchase_order,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        if instance.status == Bill.Status.PAID:
            raise serializers.ValidationError(
                {"status": "Paid bills cannot be updated."}
            )
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        vendor_id = validated_data.pop("vendor_id", None)
        purchase_order_id = validated_data.pop("purchase_order_id", serializers.empty)
        if vendor_id:
            vendor = Vendor.objects.filter(
                pk=vendor_id,
                organization=instance.organization,
            ).first()
            if not vendor:
                raise serializers.ValidationError({"vendor_id": "Vendor not found."})
            instance.vendor = vendor
        if purchase_order_id is not serializers.empty:
            if purchase_order_id is None:
                instance.purchase_order = None
            else:
                purchase_order = PurchaseOrder.objects.filter(
                    pk=purchase_order_id,
                    organization=instance.organization,
                ).first()
                if not purchase_order:
                    raise serializers.ValidationError(
                        {"purchase_order_id": "Purchase order not found."}
                    )
                instance.purchase_order = purchase_order
        requested_number = validated_data.get("bill_number")
        if requested_number:
            taken = (
                Bill.objects.filter(
                    organization=instance.organization,
                    bill_number=requested_number,
                )
                .exclude(pk=instance.pk)
                .exists()
            )
            if taken:
                raise serializers.ValidationError(
                    {"bill_number": "Bill number already exists."}
                )
        validated_data = self._apply_status_timestamps(validated_data, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
