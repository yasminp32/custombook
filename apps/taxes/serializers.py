from rest_framework import serializers

from apps.taxes import constants
from apps.taxes.models import TaxRate, TaxSettings
from apps.taxes.services import (
    international_trade_label,
    international_trade_note,
    normalize_tax_number,
    tax_number_label,
)


class TaxMemberSerializer(serializers.ModelSerializer):
    tax_id = serializers.UUIDField(source="id", read_only=True)
    rate_label = serializers.CharField(read_only=True)

    class Meta:
        model = TaxRate
        fields = ("tax_id", "name", "rate", "rate_label")
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["rate"] = f"{instance.rate:.2f}"
        return data


class TaxRateSerializer(serializers.ModelSerializer):
    tax_id = serializers.UUIDField(source="id", read_only=True)
    rate_label = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    default_label = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    class Meta:
        model = TaxRate
        fields = (
            "tax_id",
            "name",
            "display_name",
            "rate",
            "rate_label",
            "tax_type",
            "is_default",
            "default_label",
            "members",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_default_label(self, obj):
        return "Default Tax" if obj.is_default else ""

    def get_members(self, obj):
        if obj.tax_type != TaxRate.TaxType.GROUP:
            return []
        return TaxMemberSerializer(obj.members.all().order_by("name"), many=True).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["rate"] = f"{instance.rate:.2f}"
        return data


class TaxRateWriteSerializer(serializers.ModelSerializer):
    tax_type = serializers.ChoiceField(choices=constants.TAX_TYPES, required=False)
    rate = serializers.DecimalField(max_digits=7, decimal_places=2, required=False)
    tax_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = TaxRate
        fields = ("name", "rate", "tax_type", "is_default", "tax_ids")

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Tax name is required.")
        return value

    def validate_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Rate must be between 0 and 100.")
        return value

    def validate(self, attrs):
        tax_type = attrs.get("tax_type") or getattr(self.instance, "tax_type", TaxRate.TaxType.TAX)
        creating = self.instance is None
        if creating:
            attrs["tax_type"] = tax_type
        elif "tax_type" in attrs and attrs["tax_type"] != self.instance.tax_type:
            raise serializers.ValidationError({"tax_type": "Tax type cannot be changed."})

        if tax_type == TaxRate.TaxType.GROUP:
            if attrs.get("is_default"):
                raise serializers.ValidationError({"is_default": "A tax group cannot be the default tax."})
            if creating and "tax_ids" not in attrs:
                raise serializers.ValidationError({"tax_ids": "Select at least two taxes for the group."})
            return attrs

        if creating and "rate" not in attrs:
            raise serializers.ValidationError({"rate": "Rate is required."})
        if "tax_ids" in attrs:
            raise serializers.ValidationError({"tax_ids": "tax_ids is only used for a tax group."})
        return attrs


class TaxSettingsSerializer(serializers.ModelSerializer):
    tax_label = serializers.SerializerMethodField()
    registration_question = serializers.SerializerMethodField()
    international_trade_label = serializers.SerializerMethodField()
    international_trade_note = serializers.SerializerMethodField()
    vat_registration_date_label = serializers.SerializerMethodField()
    first_tax_return_from_label = serializers.SerializerMethodField()
    reporting_period_label = serializers.CharField(source="get_reporting_period_display", read_only=True)

    class Meta:
        model = TaxSettings
        fields = (
            "is_vat_registered",
            "registration_question",
            "tax_label",
            "tax_registration_number",
            "enable_international_trade",
            "international_trade_label",
            "international_trade_note",
            "vat_registration_date",
            "vat_registration_date_label",
            "first_tax_return_from",
            "first_tax_return_from_label",
            "reporting_period",
            "reporting_period_label",
            "updated_at",
        )
        read_only_fields = (
            "registration_question",
            "tax_label",
            "international_trade_label",
            "international_trade_note",
            "vat_registration_date_label",
            "first_tax_return_from_label",
            "reporting_period_label",
            "updated_at",
        )

    def _country(self, obj):
        return obj.organization.country

    def get_tax_label(self, obj):
        return tax_number_label(self._country(obj))

    def get_registration_question(self, obj):
        label = "VAT" if tax_number_label(self._country(obj)) == "TRN" else "GST"
        return f"Is your business registered for {label}?"

    def get_international_trade_label(self, obj):
        return international_trade_label(self._country(obj))

    def get_international_trade_note(self, obj):
        return international_trade_note(self._country(obj))

    def get_vat_registration_date_label(self, obj):
        return obj.vat_registration_date.strftime("%d %b %Y") if obj.vat_registration_date else ""

    def get_first_tax_return_from_label(self, obj):
        return obj.first_tax_return_from.strftime("%d %b %Y") if obj.first_tax_return_from else ""

    def validate_reporting_period(self, value):
        allowed = {item[0] for item in constants.REPORTING_PERIODS}
        if value not in allowed:
            raise serializers.ValidationError(
                "Reporting period must be one of: " + ", ".join(sorted(allowed)) + "."
            )
        return value

    def validate(self, attrs):
        registered = attrs.get("is_vat_registered", getattr(self.instance, "is_vat_registered", False))
        number = attrs.get(
            "tax_registration_number",
            getattr(self.instance, "tax_registration_number", ""),
        )
        registration_date = attrs.get(
            "vat_registration_date",
            getattr(self.instance, "vat_registration_date", None),
        )
        first_return = attrs.get(
            "first_tax_return_from",
            getattr(self.instance, "first_tax_return_from", None),
        )
        if not registered:
            return attrs

        country = self.instance.organization.country
        label = tax_number_label(country)
        errors = {}
        if not (number or "").strip():
            errors["tax_registration_number"] = f"{label} is required when the business is registered."
        else:
            try:
                attrs["tax_registration_number"] = normalize_tax_number(country, number)
            except ValueError as exc:
                errors["tax_registration_number"] = str(exc)
        if not registration_date:
            errors["vat_registration_date"] = "VAT registration date is required."
        if not first_return:
            errors["first_tax_return_from"] = "Generate first tax return from is required."
        if (
            registration_date
            and first_return
            and first_return < registration_date
        ):
            errors["first_tax_return_from"] = (
                "Generate first tax return from cannot be before the VAT registration date."
            )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class TaxPreferenceSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = TaxSettings
        fields = ("profit_margin_scheme", "title", "description", "updated_at")
        read_only_fields = ("title", "description", "updated_at")

    def get_title(self, obj):
        return constants.PROFIT_MARGIN_TITLE

    def get_description(self, obj):
        return constants.PROFIT_MARGIN_DESCRIPTION
