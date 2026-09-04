from rest_framework import serializers

from apps.branches.models import Address, Branch


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id",
            "attention",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "country",
            "postal_code",
            "fax",
            "phone_country_code",
            "phone",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class BranchSerializer(serializers.ModelSerializer):
    address = AddressSerializer(read_only=True)
    address_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Branch
        fields = (
            "id",
            "organization_id",
            "name",
            "address",
            "address_id",
            "is_primary",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BranchWriteSerializer(serializers.ModelSerializer):
    address = AddressSerializer(required=False, allow_null=True)
    address_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    organization_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Branch
        fields = (
            "organization_id",
            "name",
            "address",
            "address_id",
            "is_primary",
            "status",
        )

    def validate_status(self, value):
        if value and value not in Branch.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(Branch.Status.values)}."
            )
        return value

    def validate(self, attrs):
        address_data = attrs.pop("address", serializers.empty)
        address_id = attrs.pop("address_id", serializers.empty)

        if address_id is not serializers.empty and address_data is not serializers.empty:
            raise serializers.ValidationError(
                "Provide either address_id or address, not both."
            )

        if address_id is not serializers.empty:
            if address_id is None:
                attrs["address"] = None
            else:
                try:
                    attrs["address"] = Address.objects.get(pk=address_id)
                except Address.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {"address_id": "Address not found."}
                    ) from exc
        elif address_data is not serializers.empty:
            attrs["address"] = address_data

        return attrs

    def _upsert_address(self, branch, address_value):
        if address_value is serializers.empty:
            return

        if address_value is None:
            branch.address = None
            return

        if isinstance(address_value, Address):
            branch.address = address_value
            return

        if branch.address_id:
            for field, value in address_value.items():
                setattr(branch.address, field, value)
            branch.address.save()
        else:
            branch.address = Address.objects.create(**address_value)

    def create(self, validated_data):
        address_value = validated_data.pop("address", serializers.empty)
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        branch = Branch.objects.create(organization=organization, **validated_data)
        self._upsert_address(branch, address_value)
        branch.save()
        self._sync_primary_branch(branch)
        return branch

    def update(self, instance, validated_data):
        address_value = validated_data.pop("address", serializers.empty)
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        self._upsert_address(instance, address_value)
        instance.save()
        self._sync_primary_branch(instance)
        return instance

    def _sync_primary_branch(self, branch):
        if not branch.is_primary or not branch.organization_id:
            return

        Branch.objects.filter(
            organization_id=branch.organization_id,
            is_primary=True,
        ).exclude(pk=branch.pk).update(is_primary=False)
