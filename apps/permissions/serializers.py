from rest_framework import serializers

from apps.permissions.models import RolePermission
from apps.roles.models import Role


class RolePermissionSerializer(serializers.ModelSerializer):
    permission_id = serializers.UUIDField(source="id", read_only=True)
    role_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = RolePermission
        fields = ("permission_id", "role_id", "module", "permission_level")
        read_only_fields = fields


class RolePermissionWriteSerializer(serializers.ModelSerializer):
    role_id = serializers.UUIDField()

    class Meta:
        model = RolePermission
        fields = ("role_id", "module", "permission_level")

    def validate_role_id(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not Role.objects.filter(pk=value, organization__owner=user).exists():
            raise serializers.ValidationError("Role not found.")
        return value

    def validate_module(self, value):
        return value.strip().lower()

    def validate_permission_level(self, value):
        if value not in RolePermission.PermissionLevel.values:
            raise serializers.ValidationError(
                f"Invalid permission level. Allowed values: "
                f"{', '.join(RolePermission.PermissionLevel.values)}."
            )
        return value

    def create(self, validated_data):
        role_id = validated_data.pop("role_id")
        return RolePermission.objects.create(role_id=role_id, **validated_data)

    def update(self, instance, validated_data):
        if "role_id" in validated_data:
            instance.role_id = validated_data.pop("role_id")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
