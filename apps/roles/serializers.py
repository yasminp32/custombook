from rest_framework import serializers

from apps.roles.models import Role


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = (
            "id",
            "role_name",
            "role_code",
            "description",
            "is_system_role",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class RoleWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("role_name", "role_code", "description", "is_system_role")

    def validate_role_code(self, value):
        return value.strip().lower()

    def validate_role_name(self, value):
        return value.strip()
