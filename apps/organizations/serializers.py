import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.countries import get_countries_list
from apps.accounts.validators import validate_country_code, validate_state_for_country
from apps.organizations.constants import (
    CURRENCY_OPTIONS,
    DATE_FORMAT_OPTIONS,
    FISCAL_YEAR_OPTIONS,
    INDUSTRY_OPTIONS,
    LANGUAGE_OPTIONS,
    TIMEZONE_OPTIONS,
)
from apps.organizations.gst import get_state_from_gstin, validate_gstin
from apps.organizations.models import Organization

PORTAL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
LOGO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_LOGO_BYTES = 2 * 1024 * 1024

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    industry_label = serializers.SerializerMethodField()
    language_label = serializers.SerializerMethodField()
    timezone_label = serializers.SerializerMethodField()
    currency_label = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    fiscal_year_label = serializers.CharField(source="get_fiscal_year_display", read_only=True)
    date_format_label = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    portal_url = serializers.SerializerMethodField()
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "id",
            "organization_number",
            "name",
            "portal_name",
            "portal_url",
            "logo_url",
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
            "phone",
            "fax",
            "website",
            "update_address_in_previous_transactions",
            "use_payment_stub_address",
            "payment_stub_address_line1",
            "payment_stub_address_line2",
            "payment_stub_city",
            "payment_stub_state",
            "payment_stub_postal_code",
            "fiscal_year",
            "fiscal_year_label",
            "date_format",
            "date_format_label",
            "company_id",
            "is_current",
            "is_setup_complete",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_number",
            "logo_url",
            "portal_url",
            "is_setup_complete",
            "created_at",
            "updated_at",
        )

    def _label_for(self, options, value):
        for option in options:
            if option["value"] == value:
                return option["label"]
        return value

    def get_industry_label(self, obj):
        if not obj.industry:
            return ""
        label = self._label_for(INDUSTRY_OPTIONS, obj.industry)
        if label != obj.industry:
            return label
        return obj.get_industry_display()

    def get_date_format_label(self, obj):
        return self._label_for(DATE_FORMAT_OPTIONS, obj.date_format)

    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.logo.url)
        return obj.logo.url

    def get_portal_url(self, obj):
        if not obj.portal_name:
            return ""
        base = (getattr(settings, "PORTAL_BASE_URL", "") or "").rstrip("/")
        if base:
            return f"{base}/{obj.portal_name}"
        request = self.context.get("request")
        path = f"/portal/{obj.portal_name}"
        if request:
            return request.build_absolute_uri(path)
        return path

    def get_language_label(self, obj):
        return self._label_for(LANGUAGE_OPTIONS, obj.language)

    def get_timezone_label(self, obj):
        return self._label_for(TIMEZONE_OPTIONS, obj.timezone)

    def get_currency_label(self, obj):
        return self._label_for(CURRENCY_OPTIONS, obj.currency)

    def get_is_current(self, obj):
        current_id = self.context.get("current_organization_id")
        if current_id is not None:
            return obj.id == current_id
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return user.current_organization_id == obj.id

    def get_country_name(self, obj):
        if obj.country == "OT":
            return "Other"
        for country in get_countries_list():
            if country["code"] == obj.country:
                return country["name"]
        return obj.country


class OrganizationSetupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    industry = serializers.ChoiceField(choices=Organization.Industry.choices)
    country = serializers.CharField(max_length=2)
    state = serializers.CharField(max_length=100, allow_blank=True)
    currency = serializers.CharField(max_length=3)
    language = serializers.ChoiceField(choices=Organization.Language.choices)
    timezone = serializers.CharField(max_length=64)
    is_gst_registered = serializers.BooleanField()
    gstin = serializers.CharField(max_length=15, required=False, allow_blank=True)
    address_line1 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    portal_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    fax = serializers.CharField(max_length=20, required=False, allow_blank=True)
    website = serializers.CharField(max_length=255, required=False, allow_blank=True)
    update_address_in_previous_transactions = serializers.BooleanField(required=False)
    use_payment_stub_address = serializers.BooleanField(required=False)
    payment_stub_address_line1 = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    payment_stub_address_line2 = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    payment_stub_city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    payment_stub_state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    payment_stub_postal_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    fiscal_year = serializers.ChoiceField(
        choices=Organization.FiscalYear.choices, required=False
    )
    date_format = serializers.ChoiceField(
        choices=Organization.DateFormat.choices, required=False
    )
    company_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    logo = serializers.ImageField(required=False, allow_null=True)
    remove_logo = serializers.BooleanField(required=False, default=False)

    def validate_country(self, value):
        code = (value or "").strip().upper()
        if code == "OT":
            return code
        return validate_country_code(code)

    def validate_portal_name(self, value):
        name = (value or "").strip().lower()
        if not name:
            return ""
        if not PORTAL_NAME_RE.match(name):
            raise serializers.ValidationError(
                "Portal name can use letters, numbers, and hyphens, and must be 3 to 50 characters."
            )
        organization = self.context.get("organization")
        taken = Organization.objects.filter(portal_name=name)
        if organization:
            taken = taken.exclude(pk=organization.pk)
        if taken.exists():
            raise serializers.ValidationError("Portal name is already in use.")
        return name

    def validate_website(self, value):
        website = (value or "").strip()
        if website and "://" not in website:
            website = f"https://{website}"
        return website

    def validate_logo(self, value):
        if not value:
            return value
        content_type = getattr(value, "content_type", "") or ""
        if content_type and content_type not in LOGO_CONTENT_TYPES:
            raise serializers.ValidationError("Logo must be a JPEG, PNG, or WebP image.")
        if value.size > MAX_LOGO_BYTES:
            raise serializers.ValidationError("Logo must be 2 MB or smaller.")
        return value

    def validate(self, attrs):
        organization = self.context.get("organization")
        partial = bool(self.partial)
        state_updated_from_gstin = False

        if "country" in attrs or not partial:
            country = attrs.get("country")
        elif organization:
            country = organization.country
        else:
            country = None

        if "state" in attrs or not partial:
            state = (attrs.get("state") or "").strip()
        elif organization:
            state = organization.state or ""
        else:
            state = ""

        if "is_gst_registered" in attrs or not partial:
            is_gst_registered = bool(attrs.get("is_gst_registered"))
            gstin = (attrs.get("gstin") or "").strip().upper()
            if not gstin and organization and "gstin" not in attrs:
                gstin = organization.gstin or ""
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
                    attrs["state"] = state
                attrs["gstin"] = gstin
            elif "is_gst_registered" in attrs or not partial:
                attrs["gstin"] = ""

        if country == "IN" and attrs.get("is_gst_registered") and not state:
            raise serializers.ValidationError(
                {"state": "State is required for GST registered businesses in India."}
            )

        if "country" in attrs or "state" in attrs or not partial:
            if country == "OT":
                attrs["state"] = state
            else:
                try:
                    attrs["state"] = validate_state_for_country(country, state)
                except DjangoValidationError as exc:
                    raise serializers.ValidationError({"state": exc.messages}) from exc

        if "currency" in attrs or not partial:
            valid_currencies = {item["value"] for item in CURRENCY_OPTIONS}
            if attrs.get("currency") not in valid_currencies:
                raise serializers.ValidationError({"currency": "Unsupported currency."})

        if "timezone" in attrs or not partial:
            valid_timezones = {item["value"] for item in TIMEZONE_OPTIONS}
            if attrs.get("timezone") not in valid_timezones:
                raise serializers.ValidationError({"timezone": "Unsupported timezone."})

        if "fiscal_year" in attrs:
            valid = {item["value"] for item in FISCAL_YEAR_OPTIONS}
            if attrs["fiscal_year"] not in valid:
                raise serializers.ValidationError({"fiscal_year": "Unsupported fiscal year."})

        attrs["state_updated_from_gstin"] = state_updated_from_gstin
        return attrs

    def update_organization(self, organization):
        validated_data = self.validated_data.copy()
        state_updated_from_gstin = validated_data.pop("state_updated_from_gstin", False)
        remove_logo = validated_data.pop("remove_logo", False)
        if remove_logo and organization.logo:
            organization.logo.delete(save=False)
            organization.logo = None

        for field, value in validated_data.items():
            setattr(organization, field, value)

        organization.is_setup_complete = True
        organization.save()

        return organization, state_updated_from_gstin

    def create_organization(self, owner):
        validated_data = self.validated_data.copy()
        validated_data.pop("state_updated_from_gstin", None)
        validated_data.pop("remove_logo", None)

        organization = Organization.objects.create(
            owner=owner,
            is_setup_complete=True,
            **validated_data,
        )
        state_updated_from_gstin = self.validated_data.get("state_updated_from_gstin", False)
        return organization, state_updated_from_gstin
