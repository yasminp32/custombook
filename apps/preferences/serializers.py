import re

from rest_framework import serializers

from apps.invoices.models import Invoice
from apps.preferences import constants
from apps.preferences.models import CustomField, MileageRate, Preference
from apps.preferences.services import (
    format_number,
    live_next_number,
    unknown_placeholders,
)
from apps.quotes.models import Quote

PREFIX_RE = re.compile(r"^[A-Za-z0-9/_\-#.]{0,20}$")
ORGANIZATION_KEYS = [
    "ORGANIZATION.NAME",
    "ORGANIZATION.STREET_ADDRESS",
    "ORGANIZATION.CITY",
    "ORGANIZATION.STATE",
    "ORGANIZATION.POSTAL_CODE",
    "ORGANIZATION.COUNTRY",
    "ORGANIZATION.PHONE",
    "ORGANIZATION.EMAIL",
    "ORGANIZATION.WEBSITE",
    "ORGANIZATION.TRN_LABEL",
    "ORGANIZATION.TRN_VALUE",
]
CONTACT_KEYS = [
    "CONTACT.CONTACT_DISPLAYNAME",
    "CONTACT.CONTACT_ATTENTION",
    "CONTACT.CONTACT_ADDRESS",
    "CONTACT.CONTACT_CITY",
    "CONTACT.CONTACT_STATE",
    "CONTACT.CONTACT_CODE",
    "CONTACT.CONTACT_COUNTRY",
    "CONTACT.CONTACT_PHONE",
    "CONTACT.CONTACT_FAX",
    "CONTACT.TRN_LABEL",
    "CONTACT.TRN",
]


def validate_placeholders(value, allowed, label):
    unknown = unknown_placeholders(value, allowed)
    if unknown:
        raise serializers.ValidationError(
            f"Unknown placeholder(s) in {label}: {', '.join('${' + key + '}' for key in unknown)}."
        )
    return value


class CustomFieldSerializer(serializers.ModelSerializer):
    field_id = serializers.UUIDField(source="id", read_only=True)
    entity_label = serializers.CharField(source="get_entity_display", read_only=True)
    data_type_label = serializers.CharField(source="get_data_type_display", read_only=True)

    class Meta:
        model = CustomField
        fields = (
            "field_id",
            "entity",
            "entity_label",
            "label",
            "data_type",
            "data_type_label",
            "options",
            "is_mandatory",
            "show_in_pdf",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CustomFieldWriteSerializer(serializers.ModelSerializer):
    entity = serializers.ChoiceField(choices=constants.CUSTOM_FIELD_ENTITIES)
    label = serializers.CharField(max_length=100)
    data_type = serializers.ChoiceField(choices=constants.CUSTOM_FIELD_DATA_TYPES, required=False)
    options = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, allow_empty=True
    )

    class Meta:
        model = CustomField
        fields = (
            "entity",
            "label",
            "data_type",
            "options",
            "is_mandatory",
            "show_in_pdf",
            "is_active",
            "sort_order",
        )

    def validate_label(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Field label is required.")
        return value

    def validate(self, attrs):
        data_type = attrs.get("data_type") or getattr(self.instance, "data_type", "text")
        options = attrs.get("options")
        if options is None:
            options = list(getattr(self.instance, "options", []) or [])
        cleaned = []
        for option in options:
            option = (option or "").strip()
            if option and option not in cleaned:
                cleaned.append(option)
        if data_type == "dropdown" and not cleaned:
            raise serializers.ValidationError(
                {"options": "Dropdown fields need at least one option."}
            )
        if data_type != "dropdown":
            cleaned = []
        attrs["options"] = cleaned
        return attrs


class MileageRateSerializer(serializers.ModelSerializer):
    rate_id = serializers.UUIDField(source="id", read_only=True)
    rate = serializers.SerializerMethodField()
    start_date_label = serializers.SerializerMethodField()

    class Meta:
        model = MileageRate
        fields = ("rate_id", "start_date", "start_date_label", "rate", "created_at", "updated_at")
        read_only_fields = fields

    def get_rate(self, obj):
        return f"{obj.rate:.2f}"

    def get_start_date_label(self, obj):
        return obj.start_date.strftime("%d %b %Y")


class MileageRateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MileageRate
        fields = ("start_date", "rate")

    def validate_rate(self, value):
        if value <= 0:
            raise serializers.ValidationError("Rate must be greater than zero.")
        return value


class GeneralPreferenceSerializer(serializers.ModelSerializer):
    enabled_modules = serializers.ListField(
        child=serializers.ChoiceField(choices=constants.MODULE_OPTIONS), required=False
    )
    modules = serializers.SerializerMethodField()
    discount_type_label = serializers.CharField(source="get_discount_type_display", read_only=True)
    tax_type_label = serializers.CharField(source="get_tax_type_display", read_only=True)
    rounding_label = serializers.CharField(source="get_rounding_display", read_only=True)
    placeholders = serializers.SerializerMethodField()

    class Meta:
        model = Preference
        fields = (
            "enabled_modules",
            "modules",
            "attach_pdf_in_email",
            "encrypt_pdf",
            "discount_type",
            "discount_type_label",
            "tax_type",
            "tax_type_label",
            "rounding",
            "rounding_label",
            "enable_salesperson_field",
            "organization_address_format",
            "placeholders",
            "updated_at",
        )
        read_only_fields = ("modules", "placeholders", "updated_at")

    def get_modules(self, obj):
        enabled = set(obj.enabled_modules or [])
        return [
            {"code": code, "label": label, "enabled": code in enabled}
            for code, label in constants.MODULE_OPTIONS
        ]

    def get_placeholders(self, obj):
        return [{"label": label, "value": value} for label, value in constants.ORGANIZATION_PLACEHOLDERS]

    def validate_enabled_modules(self, value):
        seen = []
        for code in value:
            if code not in seen:
                seen.append(code)
        return seen

    def validate_organization_address_format(self, value):
        return validate_placeholders(value, ORGANIZATION_KEYS, "Organization Address Format")


class CustomersVendorsPreferenceSerializer(serializers.ModelSerializer):
    default_customer_type_label = serializers.CharField(
        source="get_default_customer_type_display", read_only=True
    )
    placeholders = serializers.SerializerMethodField()
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = Preference
        fields = (
            "default_customer_type",
            "default_customer_type_label",
            "allow_duplicate_display_name",
            "enable_credit_limit",
            "billing_address_format",
            "shipping_address_format",
            "placeholders",
            "custom_fields",
            "updated_at",
        )
        read_only_fields = ("placeholders", "custom_fields", "updated_at")

    def get_placeholders(self, obj):
        return [{"label": label, "value": value} for label, value in constants.CONTACT_PLACEHOLDERS]

    def get_custom_fields(self, obj):
        return custom_fields_for(obj.organization, "customers_vendors")

    def validate_billing_address_format(self, value):
        return validate_placeholders(value, CONTACT_KEYS, "Billing Address Format")

    def validate_shipping_address_format(self, value):
        return validate_placeholders(value, CONTACT_KEYS, "Shipping Address Format")


class ItemsPreferenceSerializer(serializers.ModelSerializer):
    inventory_start_date_label = serializers.SerializerMethodField()
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = Preference
        fields = (
            "enable_inventory",
            "inventory_start_date",
            "inventory_start_date_label",
            "notify_below_reorder_point",
            "custom_fields",
            "updated_at",
        )
        read_only_fields = ("inventory_start_date_label", "custom_fields", "updated_at")

    def get_inventory_start_date_label(self, obj):
        return obj.inventory_start_date.strftime("%d %b %Y") if obj.inventory_start_date else ""

    def get_custom_fields(self, obj):
        return custom_fields_for(obj.organization, "items")

    def validate(self, attrs):
        enable = attrs.get("enable_inventory", getattr(self.instance, "enable_inventory", False))
        start = attrs.get(
            "inventory_start_date", getattr(self.instance, "inventory_start_date", None)
        )
        if enable and not start:
            raise serializers.ValidationError(
                {"inventory_start_date": "Inventory start date is required when inventory is enabled."}
            )
        return attrs


class NumberingMixin:
    prefix_field = ""
    next_field = ""
    document_model = None
    document_number_field = ""

    def _next_number(self, obj):
        prefix = getattr(obj, self.prefix_field)
        stored = getattr(obj, self.next_field)
        return live_next_number(
            self.document_model, self.document_number_field, obj.organization, prefix, stored
        )

    def get_next_number(self, obj):
        return f"{self._next_number(obj):06d}"

    def get_next_number_preview(self, obj):
        return format_number(getattr(obj, self.prefix_field), self._next_number(obj))

    def _validate_prefix(self, value):
        value = (value or "").strip()
        if not PREFIX_RE.match(value):
            raise serializers.ValidationError(
                "Prefix may only contain letters, numbers, - _ / # . and be up to 20 characters."
            )
        return value


class QuotesPreferenceSerializer(NumberingMixin, serializers.ModelSerializer):
    prefix_field = "quote_prefix"
    next_field = "quote_next_number"
    document_model = Quote
    document_number_field = "quote_number"

    auto_generate_number = serializers.BooleanField(
        source="quote_auto_generate_number", required=False
    )
    prefix = serializers.CharField(source="quote_prefix", required=False, allow_blank=True)
    next_number = serializers.IntegerField(source="quote_next_number", required=False, min_value=1)
    next_number_display = serializers.SerializerMethodField(method_name="get_next_number")
    next_number_preview = serializers.SerializerMethodField()
    notes = serializers.CharField(source="quote_notes", required=False, allow_blank=True)
    terms_and_conditions = serializers.CharField(
        source="quote_terms", required=False, allow_blank=True
    )
    convert_to_invoice = serializers.BooleanField(
        source="quote_auto_convert_to_invoice", required=False
    )
    prefill_country_code = serializers.BooleanField(
        source="quote_prefill_country_code", required=False
    )
    default_country_code = serializers.CharField(
        source="quote_default_country_code", required=False, allow_blank=True, max_length=8
    )
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = Preference
        fields = (
            "auto_generate_number",
            "prefix",
            "next_number",
            "next_number_display",
            "next_number_preview",
            "notes",
            "terms_and_conditions",
            "convert_to_invoice",
            "prefill_country_code",
            "default_country_code",
            "custom_fields",
            "updated_at",
        )
        read_only_fields = ("next_number_display", "next_number_preview", "custom_fields", "updated_at")

    def get_custom_fields(self, obj):
        return custom_fields_for(obj.organization, "quotes")

    def validate_prefix(self, value):
        return self._validate_prefix(value)

    def validate_default_country_code(self, value):
        value = (value or "").strip()
        if value and not re.match(r"^\+?\d{1,4}$", value):
            raise serializers.ValidationError("Enter a country code such as +971.")
        if value and not value.startswith("+"):
            value = f"+{value}"
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["next_number"] = self._next_number(instance)
        return data


class InvoicesPreferenceSerializer(NumberingMixin, serializers.ModelSerializer):
    prefix_field = "invoice_prefix"
    next_field = "invoice_next_number"
    document_model = Invoice
    document_number_field = "invoice_number"

    auto_generate_number = serializers.BooleanField(
        source="invoice_auto_generate_number", required=False
    )
    prefix = serializers.CharField(source="invoice_prefix", required=False, allow_blank=True)
    next_number = serializers.IntegerField(
        source="invoice_next_number", required=False, min_value=1
    )
    next_number_display = serializers.SerializerMethodField(method_name="get_next_number")
    next_number_preview = serializers.SerializerMethodField()
    notes = serializers.CharField(source="invoice_notes", required=False, allow_blank=True)
    terms_and_conditions = serializers.CharField(
        source="invoice_terms", required=False, allow_blank=True
    )
    allow_edit_sent_invoice = serializers.BooleanField(
        source="invoice_allow_edit_sent", required=False
    )
    discount_before_tax = serializers.BooleanField(
        source="invoice_discount_before_tax", required=False
    )
    show_expense_receipts_in_pdf = serializers.BooleanField(
        source="invoice_show_expense_receipts_in_pdf", required=False
    )
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = Preference
        fields = (
            "auto_generate_number",
            "prefix",
            "next_number",
            "next_number_display",
            "next_number_preview",
            "notes",
            "terms_and_conditions",
            "allow_edit_sent_invoice",
            "discount_before_tax",
            "show_expense_receipts_in_pdf",
            "custom_fields",
            "updated_at",
        )
        read_only_fields = ("next_number_display", "next_number_preview", "custom_fields", "updated_at")

    def get_custom_fields(self, obj):
        return custom_fields_for(obj.organization, "invoices")

    def validate_prefix(self, value):
        return self._validate_prefix(value)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["next_number"] = self._next_number(instance)
        return data


class ExpensesPreferenceSerializer(serializers.ModelSerializer):
    mileage_unit_label = serializers.CharField(source="get_mileage_unit_display", read_only=True)
    mileage_category_label = serializers.CharField(
        source="get_mileage_category_display", read_only=True
    )
    mileage_rates = serializers.SerializerMethodField()
    custom_fields = serializers.SerializerMethodField()

    class Meta:
        model = Preference
        fields = (
            "mileage_unit",
            "mileage_unit_label",
            "mileage_category",
            "mileage_category_label",
            "mileage_rates",
            "custom_fields",
            "updated_at",
        )
        read_only_fields = ("mileage_rates", "custom_fields", "updated_at")

    def get_mileage_rates(self, obj):
        rates = MileageRate.objects.filter(organization=obj.organization)
        return MileageRateSerializer(rates, many=True).data

    def get_custom_fields(self, obj):
        return custom_fields_for(obj.organization, "expenses")


class VendorPortalPreferenceSerializer(serializers.ModelSerializer):
    notify_me_for_vendor_portal_activity = serializers.BooleanField(
        source="vendor_portal_notify_activity", required=False
    )
    notify_vendors_on_comment_or_reject = serializers.BooleanField(
        source="vendor_portal_notify_vendors_on_comment", required=False
    )
    allow_vendors_update_contact_details = serializers.BooleanField(
        source="vendor_portal_allow_contact_update", required=False
    )
    allow_vendors_accept_reject_purchase_orders = serializers.BooleanField(
        source="vendor_portal_allow_po_accept_reject", required=False
    )
    allow_vendors_upload_documents = serializers.BooleanField(
        source="vendor_portal_allow_document_upload", required=False
    )

    class Meta:
        model = Preference
        fields = (
            "notify_me_for_vendor_portal_activity",
            "notify_vendors_on_comment_or_reject",
            "allow_vendors_update_contact_details",
            "allow_vendors_accept_reject_purchase_orders",
            "allow_vendors_upload_documents",
            "updated_at",
        )
        read_only_fields = ("updated_at",)


class FieldsOnlyPreferenceSerializer(serializers.Serializer):
    """Sections that only expose custom fields (Credit Notes, Sales Orders, Bills, Purchase Orders)."""

    entity = None

    def to_representation(self, instance):
        return {
            "entity": self.entity,
            "custom_fields": custom_fields_for(instance.organization, self.entity),
        }


def custom_fields_for(organization, entity):
    fields = CustomField.objects.filter(organization=organization, entity=entity)
    return CustomFieldSerializer(fields, many=True).data


class AddressPreviewSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=(("organization", "Organization"), ("billing", "Billing"), ("shipping", "Shipping")),
        required=False,
        default="organization",
    )
    format = serializers.CharField(required=False, allow_blank=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    vendor_id = serializers.UUIDField(required=False, allow_null=True)
