from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from apps.users.models import User
from apps.users.services import find_system_role


class UserSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    organization_name = serializers.SerializerMethodField()
    role_id = serializers.UUIDField(read_only=True, allow_null=True)
    role_code = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    role_description = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "organization_id",
            "organization_name",
            "email",
            "full_name",
            "status",
            "status_label",
            "role_id",
            "role_code",
            "role_name",
            "role_description",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_organization_name(self, obj):
        return obj.organization.name if obj.organization_id else ""

    def get_status_label(self, obj):
        return "ACTIVE" if obj.status == User.Status.ACTIVE else "INACTIVE"

    def get_role_code(self, obj):
        return obj.role.role_code if obj.role_id else ""

    def get_role_name(self, obj):
        return obj.role.role_name if obj.role_id else ""

    def get_role_description(self, obj):
        return obj.role.description if obj.role_id else ""


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True, write_only=True)
    role = serializers.CharField(required=False, allow_blank=True, write_only=True)
    role_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = User
        fields = ("email", "password", "full_name", "name", "status", "role", "role_id")

    def validate_email(self, value):
        return value.strip().lower()

    def validate_status(self, value):
        if value and value not in User.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(User.Status.values)}."
            )
        return value

    def validate(self, attrs):
        name = (attrs.pop("name", "") or "").strip()
        if name and not attrs.get("full_name"):
            attrs["full_name"] = name
        role_code = attrs.pop("role", None)
        role_id = attrs.pop("role_id", None)
        if role_code or role_id:
            organization = self.context.get("organization") or getattr(self.instance, "organization", None)
            if not organization:
                raise serializers.ValidationError({"role": "Organization is required to set a role."})
            role = find_system_role(organization, role_id=role_id, role_code=role_code)
            if not role:
                raise serializers.ValidationError(
                    {
                        "role": (
                            "Invalid role. Allowed values: admin, staff_assigned_customers, "
                            "staff_all_customers, time_tracking."
                        )
                    }
                )
            attrs["role"] = role
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        user = User(**validated_data)
        if password:
            user.password_hash = make_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.password_hash = make_password(password)
        instance.save()
        return instance
