import re

from rest_framework import serializers

from apps.currencies import constants
from apps.currencies.models import Currency
from apps.currencies.services import catalog_entry

CODE_RE = re.compile(r"^[A-Z]{3}$")


class CurrencySerializer(serializers.ModelSerializer):
    currency_id = serializers.UUIDField(source="id", read_only=True)
    is_base = serializers.BooleanField(read_only=True)
    format = serializers.CharField(source="number_format", read_only=True)
    format_label = serializers.CharField(source="get_number_format_display", read_only=True)
    example = serializers.SerializerMethodField()

    class Meta:
        model = Currency
        fields = (
            "currency_id",
            "code",
            "symbol",
            "name",
            "decimal_places",
            "format",
            "format_label",
            "example",
            "is_base",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_example(self, obj):
        return f"{obj.symbol}{obj.format('1234567.891')}"


class CurrencyWriteSerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=3)
    symbol = serializers.CharField(max_length=10, required=False, allow_blank=True)
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    decimal_places = serializers.IntegerField(required=False)
    format = serializers.ChoiceField(
        source="number_format",
        choices=Currency.NumberFormat.choices,
        required=False,
    )

    class Meta:
        model = Currency
        fields = ("code", "symbol", "name", "decimal_places", "format")

    def validate_code(self, value):
        value = (value or "").strip().upper()
        if not CODE_RE.match(value):
            raise serializers.ValidationError("Currency code must be 3 letters, for example USD.")
        return value

    def validate_decimal_places(self, value):
        if value not in constants.DECIMAL_PLACES_OPTIONS:
            raise serializers.ValidationError(
                "Decimal places must be one of: "
                + ", ".join(str(option) for option in constants.DECIMAL_PLACES_OPTIONS)
                + "."
            )
        return value

    def validate(self, attrs):
        code = attrs.get("code") or getattr(self.instance, "code", "")
        entry = catalog_entry(code) or {}
        creating = self.instance is None

        symbol = (attrs.get("symbol") or "").strip()
        if "symbol" in attrs or creating:
            if not symbol:
                symbol = entry.get("symbol", "")
            if not symbol:
                raise serializers.ValidationError({"symbol": "Currency symbol is required."})
            attrs["symbol"] = symbol

        name = (attrs.get("name") or "").strip()
        if "name" in attrs or creating:
            if not name:
                name = entry.get("name", "")
            if not name:
                raise serializers.ValidationError({"name": "Currency name is required."})
            attrs["name"] = name

        if creating and "decimal_places" not in attrs:
            attrs["decimal_places"] = entry.get("decimal_places", 2)
        return attrs
