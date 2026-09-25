from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import serializers

from apps.organizations.gst import validate_gstin
from apps.organizations.models import Organization
from apps.payment_terms.models import PaymentTerm
from apps.users.models import User
from apps.vendors.models import Vendor, VendorPayment

ZERO = Decimal("0.00")


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


class VendorSerializer(serializers.ModelSerializer):
    vendor_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    payment_term_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    opening_balance = serializers.SerializerMethodField()
    payables = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = (
            "vendor_id",
            "organization_id",
            "display_name",
            "company_name",
            "email",
            "phone",
            "gstin",
            "payment_term_id",
            "opening_balance",
            "payables",
            "status",
            "status_label",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_opening_balance(self, obj):
        return money(obj.opening_balance)

    def get_payables(self, obj):
        return money(obj.opening_balance)


class VendorWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    payment_term_id = serializers.UUIDField(required=False, allow_null=True)
    display_name = serializers.CharField(required=False, allow_blank=True)
    opening_balance = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    payables = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Vendor
        fields = (
            "organization_id",
            "display_name",
            "company_name",
            "email",
            "phone",
            "gstin",
            "payment_term_id",
            "opening_balance",
            "payables",
            "status",
        )

    def validate_display_name(self, value):
        return (value or "").strip()

    def validate_company_name(self, value):
        return (value or "").strip()

    def validate_phone(self, value):
        return (value or "").strip()

    def validate_status(self, value):
        if not value:
            return Vendor.Status.ACTIVE
        key = str(value).strip().lower()
        if key not in Vendor.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(Vendor.Status.values)}."
            )
        return key

    def validate_email(self, value):
        email = (value or "").strip()
        if not email:
            return ""
        try:
            validate_email(email)
        except DjangoValidationError:
            raise serializers.ValidationError("Enter a valid email address.")
        return email

    def validate_gstin(self, value):
        if not value:
            return ""
        try:
            return validate_gstin(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate_payment_term_id(self, value):
        if value and not PaymentTerm.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Payment term not found.")
        return value

    def validate(self, attrs):
        display_name = attrs.get("display_name")
        if not self.partial and not self.instance and not display_name:
            raise serializers.ValidationError({"display_name": "Display name is required."})
        payables = attrs.pop("payables", None)
        if payables is not None and attrs.get("opening_balance") is None:
            attrs["opening_balance"] = payables
        if attrs.get("opening_balance") is None and not self.partial and not self.instance:
            attrs["opening_balance"] = ZERO
        return attrs

    def validate_created_by_reference(self, user):
        if not user:
            return None
        if isinstance(user, User):
            return user
        email = getattr(user, "email", None)
        if not email:
            return None
        return User.objects.filter(email__iexact=email, organization__owner=user).first()

    def create(self, validated_data):
        payment_term_id = validated_data.pop("payment_term_id", None)
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = self.validate_created_by_reference(
            validated_data.pop("created_by", None)
        )
        if payment_term_id:
            validated_data["payment_term_id"] = payment_term_id
        if not validated_data.get("status"):
            validated_data["status"] = Vendor.Status.ACTIVE
        return Vendor.objects.create(
            organization=organization,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        payment_term_id = validated_data.pop("payment_term_id", serializers.empty)
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        if payment_term_id is not serializers.empty:
            instance.payment_term_id = payment_term_id
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class VendorPaymentSerializer(serializers.ModelSerializer):
    vendor_payment_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = VendorPayment
        fields = (
            "vendor_payment_id",
            "organization_id",
            "vendor_id",
            "payment_date",
            "amount",
            "payment_mode_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class VendorPaymentWriteSerializer(serializers.ModelSerializer):
    vendor_id = serializers.UUIDField()
    organization_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = VendorPayment
        fields = (
            "organization_id",
            "vendor_id",
            "payment_date",
            "amount",
            "payment_mode_id",
        )

    def validate_vendor_id(self, value):
        if not Vendor.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Vendor not found.")
        return value

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        vendor_id = validated_data.pop("vendor_id")
        vendor = Vendor.objects.get(pk=vendor_id)
        return VendorPayment.objects.create(
            organization=vendor.organization,
            vendor=vendor,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("vendor_id", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
