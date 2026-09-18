import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.organizations.models import Organization
from apps.vendor_credits.models import VendorCredit
from apps.vendors.models import Vendor

ZERO = Decimal("0.00")
CREDIT_NOTE_NUMBER_RE = re.compile(r"^(?:VCN|VC)-(\d+)$", re.IGNORECASE)

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "AED": "AED",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

ALLOWED_STATUS_TRANSITIONS = {
    VendorCredit.Status.DRAFT: {
        VendorCredit.Status.DRAFT,
        VendorCredit.Status.OPEN,
        VendorCredit.Status.VOID,
    },
    VendorCredit.Status.OPEN: {
        VendorCredit.Status.OPEN,
        VendorCredit.Status.CLOSED,
        VendorCredit.Status.VOID,
    },
    VendorCredit.Status.CLOSED: {
        VendorCredit.Status.CLOSED,
    },
    VendorCredit.Status.VOID: {
        VendorCredit.Status.VOID,
    },
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def currency_symbol(code):
    return CURRENCY_SYMBOLS.get((code or "INR").upper(), code or "INR")


def next_credit_note_number(organization):
    numbers = VendorCredit.objects.filter(organization=organization).values_list(
        "credit_note_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = CREDIT_NOTE_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"VCN-{highest + 1:05d}"


class VendorCreditSerializer(serializers.ModelSerializer):
    vendor_credit_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    credit_date_label = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    class Meta:
        model = VendorCredit
        fields = (
            "vendor_credit_id",
            "organization_id",
            "vendor_id",
            "vendor_name",
            "credit_note_number",
            "reference_number",
            "credit_date",
            "credit_date_label",
            "amount",
            "currency",
            "currency_symbol",
            "status",
            "status_label",
            "notes",
            "closed_at",
            "voided_at",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_vendor_name(self, obj):
        if not obj.vendor:
            return ""
        return obj.vendor.display_name or obj.vendor.company_name or ""

    def get_credit_date_label(self, obj):
        if not obj.credit_date:
            return ""
        return obj.credit_date.strftime("%d %b %Y")

    def get_amount(self, obj):
        return money(obj.amount)

    def get_currency_symbol(self, obj):
        return currency_symbol(obj.currency)


class VendorCreditWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    vendor_id = serializers.UUIDField(required=False, allow_null=True)
    credit_note_number = serializers.CharField(required=False, allow_blank=True)
    credit_date = serializers.DateField(required=False, allow_null=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = VendorCredit
        fields = (
            "organization_id",
            "vendor_id",
            "credit_note_number",
            "reference_number",
            "credit_date",
            "amount",
            "currency",
            "status",
            "notes",
            "action",
        )

    def validate_credit_note_number(self, value):
        return (value or "").strip().upper()

    def validate_reference_number(self, value):
        return (value or "").strip()

    def validate_status(self, value):
        if not value:
            return VendorCredit.Status.DRAFT
        key = str(value).strip().lower()
        if key not in VendorCredit.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(VendorCredit.Status.values)}."
            )
        return key

    def validate_action(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save_as_draft": "save_as_draft",
            "draft": "save_as_draft",
            "save_as_open": "save_as_open",
            "open": "save_as_open",
            "save": "save_as_open",
            "close": "close",
            "void": "void",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save_as_draft, save_as_open, close, void."
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
            attrs["status"] = VendorCredit.Status.DRAFT
        elif action == "save_as_open":
            attrs["status"] = VendorCredit.Status.OPEN
        elif action == "close":
            attrs["status"] = VendorCredit.Status.CLOSED
        elif action == "void":
            attrs["status"] = VendorCredit.Status.VOID

        vendor_id = attrs.get("vendor_id")
        if not self.partial and not vendor_id and not self.instance:
            raise serializers.ValidationError({"vendor_id": "Vendor is required."})
        if vendor_id and not Vendor.objects.filter(pk=vendor_id).exists():
            raise serializers.ValidationError({"vendor_id": "Vendor not found."})

        if not attrs.get("credit_date") and not self.partial and not self.instance:
            attrs["credit_date"] = date.today()

        current_status = self.instance.status if self.instance else VendorCredit.Status.DRAFT
        next_status = attrs.get("status", current_status) or VendorCredit.Status.DRAFT
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if next_status not in allowed:
            raise serializers.ValidationError(
                {
                    "status": (
                        f"Cannot change status from {current_status} to {next_status}."
                    )
                }
            )

        amount = attrs.get("amount")
        if amount is None and self.instance:
            amount = self.instance.amount
        if next_status == VendorCredit.Status.OPEN and (amount is None or Decimal(amount) <= ZERO):
            raise serializers.ValidationError(
                {"amount": "Amount is required before saving as open."}
            )
        return attrs

    def _apply_status_timestamps(self, data, instance=None):
        status_value = data.get("status")
        if status_value == VendorCredit.Status.CLOSED and not (instance and instance.closed_at):
            data["closed_at"] = timezone.now()
        if status_value == VendorCredit.Status.VOID and not (instance and instance.voided_at):
            data["voided_at"] = timezone.now()
        return data

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        vendor_id = validated_data.pop("vendor_id", None)
        vendor = Vendor.objects.filter(pk=vendor_id, organization=organization).first()
        if not vendor:
            raise serializers.ValidationError({"vendor_id": "Vendor not found."})
        requested_number = (validated_data.get("credit_note_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and VendorCredit.objects.filter(
                organization=organization,
                credit_note_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["credit_note_number"] = next_credit_note_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = (
                organization.currency if organization else "INR"
            ) or "INR"
        validated_data = self._apply_status_timestamps(validated_data)
        return VendorCredit.objects.create(
            organization=organization,
            vendor=vendor,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        if instance.status in (VendorCredit.Status.CLOSED, VendorCredit.Status.VOID):
            raise serializers.ValidationError(
                {"status": "Closed or void vendor credits cannot be updated."}
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
        requested_number = validated_data.get("credit_note_number")
        if requested_number:
            taken = (
                VendorCredit.objects.filter(
                    organization=instance.organization,
                    credit_note_number=requested_number,
                )
                .exclude(pk=instance.pk)
                .exists()
            )
            if taken:
                validated_data["credit_note_number"] = next_credit_note_number(
                    instance.organization
                )
        validated_data = self._apply_status_timestamps(validated_data, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
