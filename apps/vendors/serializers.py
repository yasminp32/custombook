from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.organizations.gst import validate_gstin
from apps.organizations.models import Organization
from apps.payment_terms.models import PaymentTerm
from apps.users.models import User
from apps.vendors.models import Vendor, VendorPayment


class VendorSerializer(serializers.ModelSerializer):
    vendor_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    payment_term_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)

    class Meta:
        model = Vendor
        fields = (
            "vendor_id",
            "organization_id",
            "display_name",
            "gstin",
            "payment_term_id",
            "opening_balance",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class VendorWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    payment_term_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Vendor
        fields = (
            "organization_id",
            "display_name",
            "gstin",
            "payment_term_id",
            "opening_balance",
            "status",
        )

    def validate_status(self, value):
        if value and value not in Vendor.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(Vendor.Status.values)}."
            )
        return value

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

    def validate_created_by_reference(self, user):
        if not user:
            return None
        return User.objects.filter(email__iexact=user.email).first()

    def create(self, validated_data):
        payment_term_id = validated_data.pop("payment_term_id", None)
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        if payment_term_id:
            validated_data["payment_term_id"] = payment_term_id
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
        organization_id = validated_data.pop("organization_id", None)
        vendor_id = validated_data.pop("vendor_id")
        vendor = Vendor.objects.get(pk=vendor_id)
        organization = (
            Organization.objects.filter(pk=organization_id).first()
            if organization_id
            else vendor.organization
        )
        return VendorPayment.objects.create(
            organization=organization,
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
