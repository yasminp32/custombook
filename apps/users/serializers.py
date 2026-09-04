from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "status", "created_at", "updated_at")
        read_only_fields = fields


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("email", "password", "full_name", "status")

    def validate_email(self, value):
        return value.strip().lower()

    def validate_status(self, value):
        if value and value not in User.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(User.Status.values)}."
            )
        return value

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
