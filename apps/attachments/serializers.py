from rest_framework import serializers

from apps.organizations.models import Organization
from apps.attachments.models import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    attachment_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = (
            "attachment_id",
            "organization_id",
            "file_name",
            "mime_type",
            "file_size",
            "storage_key",
            "file_url",
            "attachable_type",
            "attachable_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_file_url(self, obj):
        if not obj.storage_key:
            return None
        request = self.context.get("request")
        if request:
            from django.conf import settings
            return request.build_absolute_uri(f"{settings.MEDIA_URL}{obj.storage_key}")
        return None


class AttachmentWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Attachment
        fields = (
            "organization_id",
            "file_name",
            "mime_type",
            "file_size",
            "storage_key",
            "attachable_type",
            "attachable_id",
        )

    def validate_file_name(self, value):
        return value.strip() if value else ""

    def validate_attachable_type(self, value):
        return value.strip().lower() if value else ""

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def create(self, validated_data):
        organization_id = validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        if organization_id and not organization:
            organization = Organization.objects.filter(pk=organization_id).first()
        return Attachment.objects.create(organization=organization, **validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
