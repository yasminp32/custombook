from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from apps.expenses.models import (
    DEFAULT_EXPENSE_CATEGORIES,
    Expense,
    ExpenseCategory,
)
from apps.organizations.models import Organization
from apps.vendors.models import Vendor

ZERO = Decimal("0.00")

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "AED": "AED",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def currency_symbol(code):
    return CURRENCY_SYMBOLS.get((code or "INR").upper(), code or "INR")


def ensure_default_categories(organization):
    if not organization:
        return ExpenseCategory.objects.none()
    existing = ExpenseCategory.objects.filter(organization=organization)
    if existing.exists():
        return existing.filter(is_active=True)
    rows = [
        ExpenseCategory(
            organization=organization,
            key=key,
            name=name,
        )
        for key, name in DEFAULT_EXPENSE_CATEGORIES
    ]
    ExpenseCategory.objects.bulk_create(rows)
    return ExpenseCategory.objects.filter(organization=organization, is_active=True)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    category_id = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = ExpenseCategory
        fields = ("category_id", "key", "name", "is_active")
        read_only_fields = fields


class ExpenseSerializer(serializers.ModelSerializer):
    expense_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    category_id = serializers.UUIDField(read_only=True, allow_null=True)
    category_name = serializers.SerializerMethodField()
    vendor_id = serializers.UUIDField(read_only=True, allow_null=True)
    vendor_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    expense_date_label = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = (
            "expense_id",
            "organization_id",
            "category_id",
            "category_name",
            "vendor_id",
            "vendor_name",
            "expense_date",
            "expense_date_label",
            "reference_number",
            "amount",
            "currency",
            "currency_symbol",
            "status",
            "status_label",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_category_name(self, obj):
        return obj.category.name if obj.category else ""

    def get_vendor_name(self, obj):
        if not obj.vendor:
            return ""
        return obj.vendor.display_name or obj.vendor.company_name or ""

    def get_expense_date_label(self, obj):
        if not obj.expense_date:
            return ""
        return obj.expense_date.strftime("%d %b %Y")

    def get_amount(self, obj):
        return money(obj.amount)

    def get_currency_symbol(self, obj):
        return currency_symbol(obj.currency)


class ExpenseWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    vendor_id = serializers.UUIDField(required=False, allow_null=True)
    expense_date = serializers.DateField(required=False, allow_null=True)
    amount = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)
    save_as_billed = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = Expense
        fields = (
            "organization_id",
            "category_id",
            "vendor_id",
            "expense_date",
            "reference_number",
            "amount",
            "currency",
            "status",
            "action",
            "save_as_billed",
        )

    def validate_reference_number(self, value):
        return (value or "").strip()

    def validate_status(self, value):
        if not value:
            return Expense.Status.UNBILLED
        key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        if key not in Expense.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(Expense.Status.values)}."
            )
        return key

    def validate_action(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save": "save",
            "save_as_unbilled": "save",
            "unbilled": "save",
            "save_as_billed": "save_as_billed",
            "billed": "save_as_billed",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save, save_as_billed."
            )
        return aliases[key]

    def validate_amount(self, value):
        if value is None:
            return ZERO
        amount = Decimal(value)
        if amount < ZERO:
            raise serializers.ValidationError("Amount cannot be negative.")
        return amount

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        action = attrs.pop("action", "") or ""
        save_as_billed = attrs.pop("save_as_billed", False)
        if save_as_billed or action == "save_as_billed":
            attrs["status"] = Expense.Status.BILLED
        elif action == "save" and not attrs.get("status"):
            attrs["status"] = Expense.Status.UNBILLED

        category_id = attrs.get("category_id")
        if not self.partial and not category_id and not self.instance:
            raise serializers.ValidationError({"category_id": "Category is required."})

        if not attrs.get("expense_date") and not self.partial and not self.instance:
            attrs["expense_date"] = date.today()

        if attrs.get("amount") is None and not self.partial and not self.instance:
            attrs["amount"] = ZERO
        return attrs

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        category_id = validated_data.pop("category_id", None)
        vendor_id = validated_data.pop("vendor_id", None)

        category = ExpenseCategory.objects.filter(
            pk=category_id,
            organization=organization,
        ).first()
        if not category:
            raise serializers.ValidationError({"category_id": "Category not found."})

        vendor = None
        if vendor_id:
            vendor = Vendor.objects.filter(
                pk=vendor_id,
                organization=organization,
            ).first()
            if not vendor:
                raise serializers.ValidationError({"vendor_id": "Vendor not found."})

        if not validated_data.get("currency"):
            validated_data["currency"] = (
                organization.currency if organization else "INR"
            ) or "INR"
        if not validated_data.get("status"):
            validated_data["status"] = Expense.Status.UNBILLED

        return Expense.objects.create(
            organization=organization,
            category=category,
            vendor=vendor,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        category_id = validated_data.pop("category_id", serializers.empty)
        vendor_id = validated_data.pop("vendor_id", serializers.empty)
        if category_id is not serializers.empty:
            category = ExpenseCategory.objects.filter(
                pk=category_id,
                organization=instance.organization,
            ).first()
            if not category:
                raise serializers.ValidationError({"category_id": "Category not found."})
            instance.category = category
        if vendor_id is not serializers.empty:
            if vendor_id is None:
                instance.vendor = None
            else:
                vendor = Vendor.objects.filter(
                    pk=vendor_id,
                    organization=instance.organization,
                ).first()
                if not vendor:
                    raise serializers.ValidationError({"vendor_id": "Vendor not found."})
                instance.vendor = vendor
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
