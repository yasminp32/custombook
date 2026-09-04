from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from apps.banking.constants import BANKING_CURRENCIES
from apps.banking.models import BankAccount, BankTransaction
from apps.banking.services import currency_label
from apps.organizations.models import Organization

ZERO = Decimal("0.00")


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


class BankAccountSerializer(serializers.ModelSerializer):
    account_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    account_type_label = serializers.CharField(source="get_account_type_display", read_only=True)
    currency_label = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()
    books_balance = serializers.SerializerMethodField()
    bank_balance = serializers.SerializerMethodField()
    books_balance_label = serializers.SerializerMethodField()
    bank_balance_label = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = (
            "account_id",
            "organization_id",
            "account_type",
            "account_type_label",
            "icon",
            "name",
            "account_code",
            "currency",
            "currency_label",
            "account_number",
            "bank_name",
            "ifsc_code",
            "description",
            "is_primary",
            "status",
            "books_balance",
            "bank_balance",
            "books_balance_label",
            "bank_balance_label",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_icon(self, obj):
        return obj.icon

    def get_currency_label(self, obj):
        return currency_label(obj.currency)

    def get_books_balance(self, obj):
        return money(obj.books_balance)

    def get_bank_balance(self, obj):
        return money(obj.bank_balance)

    def get_books_balance_label(self, obj):
        return "Amount In Zoho Books"

    def get_bank_balance_label(self, obj):
        return "Amount In Bank"


class BankAccountWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = BankAccount
        fields = (
            "organization_id",
            "account_type",
            "name",
            "account_code",
            "currency",
            "account_number",
            "bank_name",
            "ifsc_code",
            "description",
            "is_primary",
            "status",
            "books_balance",
            "bank_balance",
        )

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("Account name is required.")
        return name

    def validate_account_code(self, value):
        return (value or "").strip()

    def validate_description(self, value):
        text = value or ""
        if len(text) > 500:
            raise serializers.ValidationError("Description cannot exceed 500 characters.")
        return text

    def validate_ifsc_code(self, value):
        return (value or "").strip().upper()

    def validate_account_type(self, value):
        if value and value not in BankAccount.AccountType.values:
            raise serializers.ValidationError(
                f"Invalid account_type. Allowed values: {', '.join(BankAccount.AccountType.values)}."
            )
        return value

    def validate_status(self, value):
        if value and value not in BankAccount.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(BankAccount.Status.values)}."
            )
        return value

    def validate_currency(self, value):
        code = (value or "INR").strip().upper()
        valid = {item["value"] for item in BANKING_CURRENCIES}
        if code not in valid:
            raise serializers.ValidationError(
                f"Unsupported currency. Allowed values: {', '.join(sorted(valid))}."
            )
        return code

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def _clear_other_primary(self, organization, instance=None):
        queryset = BankAccount.objects.filter(organization=organization, is_primary=True)
        if instance:
            queryset = queryset.exclude(pk=instance.pk)
        queryset.update(is_primary=False)

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        if validated_data.get("is_primary"):
            self._clear_other_primary(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = (organization.currency if organization else None) or "INR"
        return BankAccount.objects.create(
            organization=organization,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        if validated_data.get("is_primary"):
            self._clear_other_primary(instance.organization, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class BankTransactionSerializer(serializers.ModelSerializer):
    transaction_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    account_id = serializers.UUIDField(read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    amount = serializers.SerializerMethodField()
    signed_amount = serializers.SerializerMethodField()

    class Meta:
        model = BankTransaction
        fields = (
            "transaction_id",
            "organization_id",
            "account_id",
            "account_name",
            "transaction_date",
            "transaction_type",
            "amount",
            "signed_amount",
            "description",
            "reference_number",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_amount(self, obj):
        return money(obj.amount)

    def get_signed_amount(self, obj):
        return money(obj.signed_amount)


class BankTransactionWriteSerializer(serializers.ModelSerializer):
    account_id = serializers.UUIDField()

    class Meta:
        model = BankTransaction
        fields = (
            "account_id",
            "transaction_date",
            "transaction_type",
            "amount",
            "description",
            "reference_number",
        )

    def validate_transaction_type(self, value):
        if value and value not in BankTransaction.TransactionType.values:
            raise serializers.ValidationError(
                f"Invalid transaction_type. Allowed values: {', '.join(BankTransaction.TransactionType.values)}."
            )
        return value

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def create(self, validated_data):
        account_id = validated_data.pop("account_id")
        organization = validated_data.pop("organization", None)
        account = BankAccount.objects.filter(pk=account_id, organization=organization).first()
        if not account:
            raise serializers.ValidationError({"account_id": "Bank account not found in this organization."})
        transaction = BankTransaction.objects.create(
            organization=organization,
            account=account,
            **validated_data,
        )
        signed = transaction.signed_amount
        account.books_balance = (account.books_balance or ZERO) + signed
        account.save(update_fields=["books_balance", "updated_at"])
        return transaction
