from django.utils import timezone
from rest_framework import serializers

from apps.audit_logs.models import AuditLog
from apps.organizations.models import Organization

class AuditLogSerializer(serializers.ModelSerializer):
    audit_log_id = serializers.IntegerField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    user_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = (
            "audit_log_id",
            "organization_id",
            "user_id",
            "entity_type",
            "entity_id",
            "action",
            "old_values",
            "new_values",
            "occurred_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class AuditLogWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    user_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = AuditLog
        fields = (
            "organization_id",
            "user_id",
            "entity_type",
            "entity_id",
            "action",
            "old_values",
            "new_values",
            "occurred_at",
        )

    def validate_entity_type(self, value):
        return value.strip().lower() if value else ""

    def validate_action(self, value):
        return value.strip().lower() if value else ""

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def create(self, validated_data):
        organization_id = validated_data.pop("organization_id", None)
        validated_data.pop("user_id", None)
        organization = validated_data.pop("organization", None)
        user = validated_data.pop("user", None)

        if organization_id and not organization:
            organization = Organization.objects.filter(pk=organization_id).first()

        if not validated_data.get("occurred_at"):
            validated_data["occurred_at"] = timezone.now()

        return AuditLog.objects.create(
            organization=organization,
            user=user,
            **validated_data,
        )
