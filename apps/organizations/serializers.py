from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.countries import (
    get_countries_list,
    get_states_for_country,
    is_valid_country,
)
from apps.accounts.validators import validate_country_code, validate_state_for_country
from apps.organizations.constants import (
    CURRENCY_OPTIONS,
    INDUSTRY_OPTIONS,
    LANGUAGE_OPTIONS,
    TIMEZONE_OPTIONS,
)
from apps.organizations.gst import get_state_from_gstin, validate_gstin
from apps.organizations.models import Organization

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    industry_label = serializers.SerializerMethodField()
    language_label = serializers.SerializerMethodField()
    timezone_label = serializers.SerializerMethodField()
    currency_label = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "industry",
            "industry_label",
            "country",
            "country_name",
            "state",
            "currency",
            "currency_label",
            "language",
            "language_label",
            "timezone",
            "timezone_label",
            "is_gst_registered",
            "gstin",
            "address_line1",
            "address_line2",
            "city",
            "postal_code",
            "is_setup_complete",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_setup_complete", "created_at", "updated_at")

    def _label_for(self, options, value):
        for option in options:
            if option["value"] == value:
                return option["label"]
        return value

    def get_industry_label(self, obj):
        return self._label_for(INDUSTRY_OPTIONS, obj.industry) if obj.industry else ""

    def get_language_label(self, obj):
        return self._label_for(LANGUAGE_OPTIONS, obj.language)

    def get_timezone_label(self, obj):
        return self._label_for(TIMEZONE_OPTIONS, obj.timezone)

    def get_currency_label(self, obj):
        return self._label_for(CURRENCY_OPTIONS, obj.currency)

    def get_country_name(self, obj):
        for country in get_countries_list():
            if country["code"] == obj.country:
                return country["name"]
        return obj.country


class OrganizationSetupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    industry = serializers.ChoiceField(choices=Organization.Industry.choices)
    country = serializers.CharField(max_length=2)
    state = serializers.CharField(max_length=100)
    currency = serializers.CharField(max_length=3)
    language = serializers.ChoiceField(choices=Organization.Language.choices)
    timezone = serializers.CharField(max_length=64)
    is_gst_registered = serializers.BooleanField()
    gstin = serializers.CharField(max_length=15, required=False, allow_blank=True)
    address_line1 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_country(self, value):
        return validate_country_code(value)

    def validate(self, attrs):
        country = attrs.get("country")
        state = attrs.get("state", "").strip()
        is_gst_registered = attrs.get("is_gst_registered")
        gstin = attrs.get("gstin", "").strip().upper()
        state_updated_from_gstin = False

        if is_gst_registered:
            if not gstin:
                raise serializers.ValidationError(
                    {"gstin": "GSTIN is required when the business is registered for GST."}
                )
            try:
                gstin = validate_gstin(gstin)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"gstin": exc.messages}) from exc

            gstin_state = get_state_from_gstin(gstin)
            if gstin_state and gstin_state != state:
                state = gstin_state
                state_updated_from_gstin = True
            attrs["gstin"] = gstin
        else:
            attrs["gstin"] = ""

        if country == "IN" and is_gst_registered and not state:
            raise serializers.ValidationError(
                {"state": "State is required for GST registered businesses in India."}
            )

        try:
            attrs["state"] = validate_state_for_country(country, state)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"state": exc.messages}) from exc

        valid_currencies = {item["value"] for item in CURRENCY_OPTIONS}
        if attrs.get("currency") not in valid_currencies:
            raise serializers.ValidationError({"currency": "Unsupported currency."})

        valid_timezones = {item["value"] for item in TIMEZONE_OPTIONS}
        if attrs.get("timezone") not in valid_timezones:
            raise serializers.ValidationError({"timezone": "Unsupported timezone."})

        attrs["state_updated_from_gstin"] = state_updated_from_gstin
        return attrs

    def update_organization(self, organization):
        validated_data = self.validated_data.copy()
        state_updated_from_gstin = validated_data.pop("state_updated_from_gstin", False)

        for field, value in validated_data.items():
            setattr(organization, field, value)

        organization.is_setup_complete = True
        organization.save()

        return organization, state_updated_from_gstin

    def create_organization(self, owner):
        validated_data = self.validated_data.copy()
        validated_data.pop("state_updated_from_gstin", None)

        organization = Organization.objects.create(
            owner=owner,
            is_setup_complete=True,
            **validated_data,
        )
        state_updated_from_gstin = self.validated_data.get("state_updated_from_gstin", False)
        return organization, state_updated_from_gstin
