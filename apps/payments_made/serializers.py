import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from apps.organizations.models import Organization
from apps.payments_made.models import PaymentMade
from apps.vendors.models import Vendor

ZERO = Decimal("0.00")
PAYMENT_NUMBER_RE = re.compile(r"^(?:PM|PAY)-(\d+)$", re.IGNORECASE)

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "AED": "AED",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

PAYMENT_MODE_ALIASES = {
    "cash": "cash",
    "bank_transfer": "bank_transfer",
    "bank transfer": "bank_transfer",
    "banktransfer": "bank_transfer",
    "card": "card",
    "cheque": "cheque",
    "check": "cheque",
    "upi": "upi",
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def currency_symbol(code):
    return CURRENCY_SYMBOLS.get((code or "INR").upper(), code or "INR")


def next_payment_number(organization):
    numbers = PaymentMade.objects.filter(organization=organization).values_list(
        "payment_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = PAYMENT_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"PM-{highest + 1:05d}"


class PaymentMadeSerializer(serializers.ModelSerializer):
    payment_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    payment_mode_label = serializers.CharField(source="get_payment_mode_display", read_only=True)
    payment_mode_list_label = serializers.SerializerMethodField()
    payment_date_label = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    class Meta:
        model = PaymentMade
        fields = (
            "payment_id",
            "organization_id",
            "vendor_id",
            "vendor_name",
            "payment_number",
            "payment_date",
            "payment_date_label",
            "payment_mode",
            "payment_mode_label",
            "payment_mode_list_label",
            "reference_number",
            "amount",
            "currency",
            "currency_symbol",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_vendor_name(self, obj):
        if not obj.vendor:
            return ""
        return obj.vendor.display_name or obj.vendor.company_name or ""

    def get_payment_date_label(self, obj):
        if not obj.payment_date:
            return ""
        return obj.payment_date.strftime("%d %b %Y")

    def get_payment_mode_list_label(self, obj):
        return (obj.get_payment_mode_display() or "").upper()

    def get_amount(self, obj):
        return money(obj.amount)

    def get_currency_symbol(self, obj):
        return currency_symbol(obj.currency)


class PaymentMadeWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    vendor_id = serializers.UUIDField(required=False, allow_null=True)
    payment_number = serializers.CharField(required=False, allow_blank=True)
    payment_date = serializers.DateField(required=False, allow_null=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = PaymentMade
        fields = (
            "organization_id",
            "vendor_id",
            "payment_number",
            "payment_date",
            "payment_mode",
            "reference_number",
            "amount",
            "currency",
            "notes",
        )

    def validate_payment_number(self, value):
        return (value or "").strip().upper()

    def validate_reference_number(self, value):
        return (value or "").strip()

    def validate_payment_mode(self, value):
        if not value:
            return PaymentMade.PaymentMode.BANK_TRANSFER
        key = str(value).strip().lower()
        mapped = PAYMENT_MODE_ALIASES.get(key) or PAYMENT_MODE_ALIASES.get(key.replace(" ", "_"))
        if not mapped:
            raise serializers.ValidationError(
                "Invalid payment mode. Allowed values: cash, bank_transfer, card, cheque, upi."
            )
        return mapped

    def validate_amount(self, value):
        amount = Decimal(value or 0)
        if amount < ZERO:
            raise serializers.ValidationError("Amount cannot be negative.")
        return amount

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        vendor_id = attrs.get("vendor_id")
        if not self.partial and not vendor_id and not self.instance:
            raise serializers.ValidationError({"vendor_id": "Vendor is required."})
        if vendor_id and not Vendor.objects.filter(pk=vendor_id).exists():
            raise serializers.ValidationError({"vendor_id": "Vendor not found."})

        if not attrs.get("payment_date") and not self.partial and not self.instance:
            attrs["payment_date"] = date.today()
        return attrs

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        vendor_id = validated_data.pop("vendor_id", None)

        vendor = Vendor.objects.filter(pk=vendor_id, organization=organization).first()
        if not vendor:
            raise serializers.ValidationError({"vendor_id": "Vendor not found."})

        requested_number = (validated_data.get("payment_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and PaymentMade.objects.filter(
                organization=organization,
                payment_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["payment_number"] = next_payment_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = (
                organization.currency if organization else "INR"
            ) or "INR"
        if not validated_data.get("payment_mode"):
            validated_data["payment_mode"] = PaymentMade.PaymentMode.BANK_TRANSFER

        return PaymentMade.objects.create(
            organization=organization,
            vendor=vendor,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
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
        requested_number = validated_data.get("payment_number")
        if requested_number:
            taken = (
                PaymentMade.objects.filter(
                    organization=instance.organization,
                    payment_number=requested_number,
                )
                .exclude(pk=instance.pk)
                .exists()
            )
            if taken:
                validated_data["payment_number"] = next_payment_number(instance.organization)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
