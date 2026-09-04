from rest_framework import serializers

from apps.organizations.models import Organization
from apps.payment_terms.models import PaymentTerm


class PaymentTermSerializer(serializers.ModelSerializer):
    payment_term_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = PaymentTerm
        fields = (
            "payment_term_id",
            "organization_id",
            "name",
            "due_days",
            "is_default",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PaymentTermWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = PaymentTerm
        fields = ("organization_id", "name", "due_days", "is_default")

    def validate_name(self, value):
        return value.strip()

    def validate_due_days(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("due_days cannot be negative.")
        return value

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def create(self, validated_data):
        organization_id = validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        if organization_id and not organization:
            organization = Organization.objects.filter(pk=organization_id).first()
        payment_term = PaymentTerm.objects.create(
            organization=organization,
            **validated_data,
        )
        self._sync_default(payment_term)
        return payment_term

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        self._sync_default(instance)
        return instance

    def _sync_default(self, payment_term):
        if not payment_term.is_default or not payment_term.organization_id:
            return
        PaymentTerm.objects.filter(
            organization_id=payment_term.organization_id,
            is_default=True,
        ).exclude(pk=payment_term.pk).update(is_default=False)
