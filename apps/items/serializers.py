from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from apps.items.models import Item
from apps.organizations.models import Organization
from apps.users.models import User
from apps.vendors.models import Vendor

ZERO = Decimal("0.00")


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


class ItemSerializer(serializers.ModelSerializer):
    item_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    preferred_vendor_id = serializers.UUIDField(read_only=True, allow_null=True)
    preferred_vendor_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    image_url = serializers.SerializerMethodField()
    selling_price = serializers.SerializerMethodField()
    cost_price = serializers.SerializerMethodField()
    margin = serializers.SerializerMethodField()
    opening_stock = serializers.SerializerMethodField()
    stock_on_hand = serializers.SerializerMethodField()
    rate_per_unit = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            "item_id",
            "organization_id",
            "item_type",
            "name",
            "sku",
            "unit",
            "image_url",
            "is_excise_product",
            "status",
            "synced_with_crm",
            "sales_enabled",
            "selling_price",
            "sales_account",
            "sales_description",
            "tax",
            "purchase_enabled",
            "cost_price",
            "purchase_account",
            "purchase_description",
            "preferred_vendor_id",
            "preferred_vendor_name",
            "track_inventory",
            "inventory_account",
            "opening_stock",
            "stock_on_hand",
            "rate_per_unit",
            "valuation_method",
            "margin",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_preferred_vendor_name(self, obj):
        if not obj.preferred_vendor:
            return None
        return obj.preferred_vendor.display_name

    def get_selling_price(self, obj):
        return money(obj.selling_price)

    def get_cost_price(self, obj):
        return money(obj.cost_price)

    def get_margin(self, obj):
        return money(obj.margin)

    def get_opening_stock(self, obj):
        return money(obj.opening_stock)

    def get_stock_on_hand(self, obj):
        return money(obj.opening_stock)

    def get_rate_per_unit(self, obj):
        return money(obj.rate_per_unit)


class ItemWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    preferred_vendor_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Item
        fields = (
            "organization_id",
            "item_type",
            "name",
            "sku",
            "unit",
            "image",
            "is_excise_product",
            "status",
            "synced_with_crm",
            "sales_enabled",
            "selling_price",
            "sales_account",
            "sales_description",
            "tax",
            "purchase_enabled",
            "cost_price",
            "purchase_account",
            "purchase_description",
            "preferred_vendor_id",
            "track_inventory",
            "inventory_account",
            "opening_stock",
            "rate_per_unit",
            "valuation_method",
        )

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("Item name is required.")
        return name

    def validate_sku(self, value):
        return (value or "").strip().upper()

    def validate_unit(self, value):
        return (value or "").strip()

    def validate_item_type(self, value):
        if value and value not in Item.ItemType.values:
            raise serializers.ValidationError(
                f"Invalid item_type. Allowed values: {', '.join(Item.ItemType.values)}."
            )
        return value

    def validate_status(self, value):
        if value and value not in Item.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(Item.Status.values)}."
            )
        return value

    def validate_valuation_method(self, value):
        if value and value not in Item.ValuationMethod.values:
            raise serializers.ValidationError(
                f"Invalid valuation_method. Allowed values: {', '.join(Item.ValuationMethod.values)}."
            )
        return value

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate_preferred_vendor_id(self, value):
        if value and not Vendor.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Vendor not found.")
        return value

    def validate_created_by_reference(self, user):
        if not user:
            return None
        return User.objects.filter(
            email__iexact=user.email,
            organization__owner=user,
        ).first()

    def _current(self, attrs, field, default=None):
        if field in attrs:
            return attrs[field]
        if self.instance is not None:
            return getattr(self.instance, field)
        return default

    def validate(self, attrs):
        sales_enabled = self._current(attrs, "sales_enabled", True)
        purchase_enabled = self._current(attrs, "purchase_enabled", True)
        track_inventory = self._current(attrs, "track_inventory", False)
        item_type = self._current(attrs, "item_type", Item.ItemType.GOODS)

        if sales_enabled:
            selling_price = self._current(attrs, "selling_price")
            sales_account = self._current(attrs, "sales_account") or "Sales"
            if selling_price is None:
                raise serializers.ValidationError(
                    {"selling_price": "Selling price is required when sales information is enabled."}
                )
            attrs["sales_account"] = sales_account

        if purchase_enabled:
            cost_price = self._current(attrs, "cost_price")
            purchase_account = self._current(attrs, "purchase_account") or "Cost of Goods Sold"
            if cost_price is None:
                raise serializers.ValidationError(
                    {"cost_price": "Cost price is required when purchase information is enabled."}
                )
            attrs["purchase_account"] = purchase_account

        if item_type == Item.ItemType.SERVICE:
            attrs["track_inventory"] = False
            track_inventory = False

        if track_inventory:
            inventory_account = self._current(attrs, "inventory_account") or "Inventory Asset"
            valuation_method = self._current(attrs, "valuation_method") or Item.ValuationMethod.FIFO
            attrs["inventory_account"] = inventory_account
            attrs["valuation_method"] = valuation_method
            if self._current(attrs, "opening_stock") is None:
                attrs["opening_stock"] = ZERO
            if self._current(attrs, "rate_per_unit") is None:
                attrs["rate_per_unit"] = ZERO

        return attrs

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        preferred_vendor_id = validated_data.pop("preferred_vendor_id", None)
        preferred_vendor = None
        if preferred_vendor_id:
            preferred_vendor = Vendor.objects.filter(
                pk=preferred_vendor_id,
                organization=organization,
            ).first()
            if preferred_vendor_id and not preferred_vendor:
                raise serializers.ValidationError(
                    {"preferred_vendor_id": "Vendor not found in this organization."}
                )
        return Item.objects.create(
            organization=organization,
            created_by=created_by,
            preferred_vendor=preferred_vendor,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        preferred_vendor_id = validated_data.pop("preferred_vendor_id", None)
        if "preferred_vendor_id" in self.initial_data:
            if preferred_vendor_id:
                vendor = Vendor.objects.filter(
                    pk=preferred_vendor_id,
                    organization=instance.organization,
                ).first()
                if not vendor:
                    raise serializers.ValidationError(
                        {"preferred_vendor_id": "Vendor not found in this organization."}
                    )
                instance.preferred_vendor = vendor
            else:
                instance.preferred_vendor = None
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
