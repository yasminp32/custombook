from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.countries import COUNTRY_NAMES, get_states_for_country
from apps.branches.models import Address, addresses_owned_by
from apps.branches.serializers import AddressSerializer
from apps.customers.constants import (
    ACCOUNTS_RECEIVABLE,
    ACCOUNTS_RECEIVABLE_ALIASES,
    CUSTOMER_CURRENCIES,
    CUSTOMER_TYPES,
    PAYMENT_TERM_ALIASES,
    PAYMENT_TERMS,
    PORTAL_LANGUAGE_ALIASES,
    PORTAL_LANGUAGES,
    SALUTATION_ALIASES,
    SALUTATIONS,
    SOCIAL_PLATFORMS,
    TAX_TREATMENT_ALIASES,
    TAX_TREATMENTS,
    normalize_choice,
)
from apps.customers.models import (
    Customer,
    CustomerAddress,
    CustomerContactPerson,
    CustomerPayment,
    CustomerSocialLink,
)
from apps.organizations.gst import validate_gstin
from apps.organizations.models import Organization
from apps.users.models import User

ZERO = Decimal("0.00")
CURRENCY_KEYS = {key for key, _ in CUSTOMER_CURRENCIES}
COUNTRY_NAME_TO_CODE = {name.lower(): code for code, name in COUNTRY_NAMES.items()}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def normalize_country(value):
    if not value:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    if len(raw) == 2:
        return raw.upper()
    mapped = COUNTRY_NAME_TO_CODE.get(raw.lower())
    if mapped:
        return mapped
    return raw[:2].upper()


def map_address_payload(data):
    if not data:
        return {}
    country = normalize_country(
        data.get("country") or data.get("country_region") or data.get("country/region")
    )
    return {
        "attention": (data.get("attention") or "").strip(),
        "address_line1": (
            data.get("street1")
            or data.get("street_1")
            or data.get("address_line1")
            or ""
        ).strip(),
        "address_line2": (
            data.get("street2")
            or data.get("street_2")
            or data.get("address_line2")
            or ""
        ).strip(),
        "city": (data.get("city") or "").strip(),
        "state": (data.get("state") or "").strip(),
        "country": country,
        "postal_code": (
            data.get("zip_code") or data.get("zip") or data.get("postal_code") or ""
        ).strip(),
        "fax": (data.get("fax") or "").strip(),
        "phone_country_code": (data.get("phone_country_code") or data.get("country_code") or "+91").strip()
        or "+91",
        "phone": (data.get("phone") or data.get("phone_number") or "").strip(),
    }


def address_to_form(address):
    if not address:
        return None
    return {
        "attention": address.attention,
        "country": address.country,
        "street1": address.address_line1,
        "street2": address.address_line2,
        "city": address.city,
        "state": address.state,
        "zip_code": address.postal_code,
        "fax": address.fax,
        "phone_country_code": address.phone_country_code or "+91",
        "phone": address.phone,
    }


def upsert_customer_address(customer, address_type, payload):
    if payload is None:
        CustomerAddress.objects.filter(customer=customer, address_type=address_type).delete()
        return
    mapped = map_address_payload(payload)
    customer_address = CustomerAddress.objects.filter(
        customer=customer,
        address_type=address_type,
    ).select_related("address").first()
    if customer_address:
        if customer_address.address_id:
            for field, value in mapped.items():
                setattr(customer_address.address, field, value)
            customer_address.address.save()
        else:
            customer_address.address = Address.objects.create(**mapped)
            customer_address.save()
        return
    address = Address.objects.create(**mapped)
    CustomerAddress.objects.create(
        customer=customer,
        address=address,
        address_type=address_type,
    )


def validate_choice_or_blank(value, aliases, allowed, field_name=None):
    if value in (None, ""):
        return ""
    try:
        return normalize_choice(value, aliases, allowed)
    except ValueError as exc:
        raise serializers.ValidationError(str(exc)) from exc


class NestedAddressFormSerializer(serializers.Serializer):
    attention = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)
    country_region = serializers.CharField(required=False, allow_blank=True, write_only=True)
    street1 = serializers.CharField(required=False, allow_blank=True)
    street2 = serializers.CharField(required=False, allow_blank=True)
    address_line1 = serializers.CharField(required=False, allow_blank=True, write_only=True)
    address_line2 = serializers.CharField(required=False, allow_blank=True, write_only=True)
    city = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    zip_code = serializers.CharField(required=False, allow_blank=True)
    postal_code = serializers.CharField(required=False, allow_blank=True, write_only=True)
    fax = serializers.CharField(required=False, allow_blank=True)
    phone_country_code = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)


class CustomerContactPersonSerializer(serializers.ModelSerializer):
    contact_person_id = serializers.UUIDField(source="id", read_only=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = CustomerContactPerson
        fields = (
            "contact_person_id",
            "customer_id",
            "salutation",
            "first_name",
            "last_name",
            "email",
            "work_phone_country_code",
            "work_phone",
            "mobile_country_code",
            "mobile",
            "designation",
            "department",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CustomerContactPersonWriteSerializer(serializers.ModelSerializer):
    contact_person_id = serializers.UUIDField(required=False)
    customer_id = serializers.UUIDField(required=False)
    work_phone_code = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )
    mobile_phone_code = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )
    mobile_phone = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = CustomerContactPerson
        fields = (
            "contact_person_id",
            "customer_id",
            "salutation",
            "first_name",
            "last_name",
            "email",
            "work_phone_country_code",
            "work_phone_code",
            "work_phone",
            "mobile_country_code",
            "mobile_phone_code",
            "mobile",
            "mobile_phone",
            "designation",
            "department",
        )

    def validate_email(self, value):
        return value.strip().lower() if value else ""

    def validate_salutation(self, value):
        return validate_choice_or_blank(
            value,
            SALUTATION_ALIASES,
            {key for key, _ in SALUTATIONS},
            "salutation",
        )

    def validate(self, attrs):
        if attrs.get("work_phone_code") and not attrs.get("work_phone_country_code"):
            attrs["work_phone_country_code"] = attrs["work_phone_code"]
        if attrs.get("mobile_phone_code") and not attrs.get("mobile_country_code"):
            attrs["mobile_country_code"] = attrs["mobile_phone_code"]
        if attrs.get("mobile_phone") and not attrs.get("mobile"):
            attrs["mobile"] = attrs["mobile_phone"]
        attrs.pop("work_phone_code", None)
        attrs.pop("mobile_phone_code", None)
        attrs.pop("mobile_phone", None)
        if not self.partial:
            has_name = (attrs.get("first_name") or "").strip() or (attrs.get("last_name") or "").strip()
            if not has_name:
                raise serializers.ValidationError(
                    {"first_name": "Contact person first name or last name is required."}
                )
        return attrs

    def create(self, validated_data):
        validated_data.pop("contact_person_id", None)
        customer_id = validated_data.pop("customer_id", None)
        customer = validated_data.pop("customer", None)
        if customer is None and customer_id:
            customer = Customer.objects.get(pk=customer_id)
        return CustomerContactPerson.objects.create(customer=customer, **validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("contact_person_id", None)
        validated_data.pop("customer_id", None)
        validated_data.pop("customer", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class CustomerSocialLinkSerializer(serializers.ModelSerializer):
    social_link_id = serializers.UUIDField(source="id", read_only=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = CustomerSocialLink
        fields = ("social_link_id", "customer_id", "platform", "url")
        read_only_fields = fields


class CustomerSocialLinkWriteSerializer(serializers.ModelSerializer):
    social_link_id = serializers.UUIDField(required=False)
    customer_id = serializers.UUIDField(required=False)

    class Meta:
        model = CustomerSocialLink
        fields = ("social_link_id", "customer_id", "platform", "url")

    def validate_platform(self, value):
        allowed = {key for key, _ in SOCIAL_PLATFORMS}
        key = (value or "website").strip().lower()
        if key not in allowed:
            raise serializers.ValidationError(
                f"Invalid platform. Allowed values: {', '.join(sorted(allowed))}."
            )
        return key

    def create(self, validated_data):
        validated_data.pop("social_link_id", None)
        customer_id = validated_data.pop("customer_id", None)
        customer = validated_data.pop("customer", None)
        if customer is None and customer_id:
            customer = Customer.objects.get(pk=customer_id)
        return CustomerSocialLink.objects.create(customer=customer, **validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("social_link_id", None)
        validated_data.pop("customer_id", None)
        validated_data.pop("customer", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class CustomerSerializer(serializers.ModelSerializer):
    customer_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)
    receivables = serializers.SerializerMethodField()
    unused_credits = serializers.SerializerMethodField()
    opening_balance = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    billing_address = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()
    contact_persons = CustomerContactPersonSerializer(many=True, read_only=True)
    social_links = CustomerSocialLinkSerializer(many=True, read_only=True)
    allow_portal_access = serializers.BooleanField(source="portal_enabled", read_only=True)

    class Meta:
        model = Customer
        fields = (
            "customer_id",
            "organization_id",
            "customer_type",
            "salutation",
            "first_name",
            "last_name",
            "name",
            "display_name",
            "company_name",
            "initials",
            "email",
            "phone_country_code",
            "phone",
            "mobile_country_code",
            "mobile",
            "gstin",
            "tax_treatment",
            "place_of_supply",
            "currency",
            "currency_id",
            "accounts_receivable",
            "payment_term_id",
            "payment_terms",
            "opening_balance",
            "receivables",
            "unused_credits",
            "synced_with_crm",
            "portal_enabled",
            "allow_portal_access",
            "portal_language",
            "website",
            "remarks",
            "billing_address",
            "shipping_address",
            "contact_persons",
            "social_links",
            "is_overdue",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_receivables(self, obj):
        return money(obj.receivables)

    def get_unused_credits(self, obj):
        return money(obj.unused_credits)

    def get_opening_balance(self, obj):
        return money(obj.opening_balance)

    def get_currency(self, obj):
        if obj.currency:
            return obj.currency
        if obj.organization and obj.organization.currency:
            return obj.organization.currency
        return "INR"

    def get_billing_address(self, obj):
        return self._address_of_type(obj, CustomerAddress.AddressType.BILLING)

    def get_shipping_address(self, obj):
        return self._address_of_type(obj, CustomerAddress.AddressType.SHIPPING)

    def _address_of_type(self, obj, address_type):
        addresses = getattr(obj, "_prefetched_objects_cache", {}).get("addresses")
        queryset = addresses if addresses is not None else obj.addresses.all()
        for customer_address in queryset:
            if customer_address.address_type == address_type:
                return address_to_form(customer_address.address)
        return None


class CustomerWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, write_only=True)
    customer_type = serializers.CharField(required=False, allow_blank=True)
    allow_portal_access = serializers.BooleanField(
        required=False,
        write_only=True,
    )
    enable_portal = serializers.BooleanField(required=False, write_only=True)
    billing_address = NestedAddressFormSerializer(required=False, allow_null=True)
    shipping_address = NestedAddressFormSerializer(required=False, allow_null=True)
    contact_persons = CustomerContactPersonWriteSerializer(many=True, required=False)
    social_links = CustomerSocialLinkWriteSerializer(many=True, required=False)
    currency = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Customer
        fields = (
            "organization_id",
            "name",
            "customer_type",
            "salutation",
            "first_name",
            "last_name",
            "display_name",
            "company_name",
            "email",
            "phone_country_code",
            "phone",
            "mobile_country_code",
            "mobile",
            "gstin",
            "tax_treatment",
            "place_of_supply",
            "currency",
            "currency_id",
            "accounts_receivable",
            "payment_term_id",
            "payment_terms",
            "opening_balance",
            "receivables",
            "unused_credits",
            "synced_with_crm",
            "portal_enabled",
            "allow_portal_access",
            "enable_portal",
            "portal_language",
            "website",
            "remarks",
            "billing_address",
            "shipping_address",
            "contact_persons",
            "social_links",
            "is_overdue",
            "status",
        )

    def validate_status(self, value):
        if value and value not in Customer.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(Customer.Status.values)}."
            )
        return value

    def validate_gstin(self, value):
        if not value:
            return ""
        try:
            return validate_gstin(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_email(self, value):
        return value.strip().lower() if value else ""

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate_customer_type(self, value):
        return validate_choice_or_blank(
            value,
            {"business": "business", "individual": "individual"},
            {key for key, _ in CUSTOMER_TYPES},
            "customer_type",
        ) or Customer.CustomerType.BUSINESS

    def validate_salutation(self, value):
        return validate_choice_or_blank(
            value,
            SALUTATION_ALIASES,
            {key for key, _ in SALUTATIONS},
            "salutation",
        )

    def validate_tax_treatment(self, value):
        return validate_choice_or_blank(
            value,
            TAX_TREATMENT_ALIASES,
            {key for key, _ in TAX_TREATMENTS},
            "tax_treatment",
        )

    def validate_payment_terms(self, value):
        return validate_choice_or_blank(
            value,
            PAYMENT_TERM_ALIASES,
            {key for key, _ in PAYMENT_TERMS},
            "payment_terms",
        )

    def validate_accounts_receivable(self, value):
        return validate_choice_or_blank(
            value,
            ACCOUNTS_RECEIVABLE_ALIASES,
            {key for key, _ in ACCOUNTS_RECEIVABLE},
            "accounts_receivable",
        )

    def validate_portal_language(self, value):
        return validate_choice_or_blank(
            value,
            PORTAL_LANGUAGE_ALIASES,
            {key for key, _ in PORTAL_LANGUAGES},
            "portal_language",
        )

    def validate_currency(self, value):
        if not value:
            return "INR"
        code = str(value).strip().upper()
        if "-" in code:
            code = code.split("-", 1)[0].strip()
        if code not in CURRENCY_KEYS:
            raise serializers.ValidationError(
                f"Invalid currency. Allowed values: {', '.join(sorted(CURRENCY_KEYS))}."
            )
        return code

    def validate_place_of_supply(self, value):
        if not value:
            return ""
        state = str(value).strip()
        states = get_states_for_country("IN")
        match = next((item for item in states if item.lower() == state.lower()), None)
        if not match:
            raise serializers.ValidationError("Invalid place of supply.")
        return match

    def validate_created_by_reference(self, user):
        if not user:
            return None
        return User.objects.filter(
            email__iexact=user.email,
            organization__owner=user,
        ).first()

    def validate(self, attrs):
        name = (attrs.pop("name", None) or "").strip()
        display_name = (attrs.get("display_name") or "").strip()
        if name and not display_name:
            attrs["display_name"] = name
            display_name = name
        first_name = (attrs.get("first_name") or "").strip()
        last_name = (attrs.get("last_name") or "").strip()
        if not display_name and (first_name or last_name):
            display_name = " ".join(part for part in (first_name, last_name) if part)
            attrs["display_name"] = display_name
        if not self.partial and not display_name and not (attrs.get("company_name") or "").strip():
            raise serializers.ValidationError(
                {"display_name": "Display name is required."}
            )

        portal_alias = attrs.pop("allow_portal_access", serializers.empty)
        enable_portal = attrs.pop("enable_portal", serializers.empty)
        if portal_alias is not serializers.empty:
            attrs["portal_enabled"] = bool(portal_alias)
        elif enable_portal is not serializers.empty:
            attrs["portal_enabled"] = bool(enable_portal)

        if attrs.get("receivables") is None and attrs.get("opening_balance") is not None:
            opening = attrs["opening_balance"] or ZERO
            if opening > 0:
                attrs["receivables"] = opening
        return attrs

    def _save_nested(self, customer, nested):
        billing = nested.get("billing_address", serializers.empty)
        shipping = nested.get("shipping_address", serializers.empty)
        if billing is not serializers.empty:
            upsert_customer_address(
                customer,
                CustomerAddress.AddressType.BILLING,
                billing,
            )
        if shipping is not serializers.empty:
            upsert_customer_address(
                customer,
                CustomerAddress.AddressType.SHIPPING,
                shipping,
            )

        contact_persons = nested.get("contact_persons", serializers.empty)
        if contact_persons is not serializers.empty:
            customer.contact_persons.all().delete()
            for item in contact_persons:
                item.pop("contact_person_id", None)
                item.pop("customer_id", None)
                CustomerContactPerson.objects.create(customer=customer, **item)

        social_links = nested.get("social_links", serializers.empty)
        if social_links is not serializers.empty:
            customer.social_links.all().delete()
            for item in social_links:
                item.pop("social_link_id", None)
                item.pop("customer_id", None)
                CustomerSocialLink.objects.create(customer=customer, **item)

    def create(self, validated_data):
        nested = {
            "billing_address": validated_data.pop("billing_address", serializers.empty),
            "shipping_address": validated_data.pop("shipping_address", serializers.empty),
            "contact_persons": validated_data.pop("contact_persons", serializers.empty),
            "social_links": validated_data.pop("social_links", serializers.empty),
        }
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        customer = Customer.objects.create(
            organization=organization,
            created_by=created_by,
            **validated_data,
        )
        self._save_nested(customer, nested)
        return customer

    def update(self, instance, validated_data):
        nested = {
            "billing_address": validated_data.pop("billing_address", serializers.empty),
            "shipping_address": validated_data.pop("shipping_address", serializers.empty),
            "contact_persons": validated_data.pop("contact_persons", serializers.empty),
            "social_links": validated_data.pop("social_links", serializers.empty),
        }
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        self._save_nested(instance, nested)
        return instance


class CustomerAddressSerializer(serializers.ModelSerializer):
    customer_address_id = serializers.UUIDField(source="id", read_only=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    address_id = serializers.UUIDField(read_only=True, allow_null=True)
    address = AddressSerializer(read_only=True)

    class Meta:
        model = CustomerAddress
        fields = (
            "customer_address_id",
            "customer_id",
            "address_id",
            "address",
            "address_type",
        )
        read_only_fields = fields


class CustomerAddressWriteSerializer(serializers.ModelSerializer):
    customer_id = serializers.UUIDField()
    address_id = serializers.UUIDField(required=False, allow_null=True)
    address = AddressSerializer(required=False, allow_null=True)
    attention = serializers.CharField(required=False, allow_blank=True, write_only=True)
    street1 = serializers.CharField(required=False, allow_blank=True, write_only=True)
    street2 = serializers.CharField(required=False, allow_blank=True, write_only=True)
    city = serializers.CharField(required=False, allow_blank=True, write_only=True)
    state = serializers.CharField(required=False, allow_blank=True, write_only=True)
    country = serializers.CharField(required=False, allow_blank=True, write_only=True)
    zip_code = serializers.CharField(required=False, allow_blank=True, write_only=True)
    fax = serializers.CharField(required=False, allow_blank=True, write_only=True)
    phone_country_code = serializers.CharField(required=False, allow_blank=True, write_only=True)
    phone = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = CustomerAddress
        fields = (
            "customer_id",
            "address_id",
            "address",
            "address_type",
            "attention",
            "street1",
            "street2",
            "city",
            "state",
            "country",
            "zip_code",
            "fax",
            "phone_country_code",
            "phone",
        )

    def validate_address_type(self, value):
        if value and value not in CustomerAddress.AddressType.values:
            raise serializers.ValidationError(
                f"Invalid address type. Allowed values: "
                f"{', '.join(CustomerAddress.AddressType.values)}."
            )
        return value

    def validate(self, attrs):
        flat_keys = (
            "attention",
            "street1",
            "street2",
            "city",
            "state",
            "country",
            "zip_code",
            "fax",
            "phone_country_code",
            "phone",
        )
        flat_data = {key: attrs.pop(key) for key in flat_keys if key in attrs}
        address_data = attrs.pop("address", serializers.empty)
        address_id = attrs.pop("address_id", serializers.empty)

        if flat_data and address_data is serializers.empty:
            address_data = map_address_payload(flat_data)

        if address_id is not serializers.empty and address_data is not serializers.empty:
            raise serializers.ValidationError(
                "Provide either address_id or address, not both."
            )

        if address_id is not serializers.empty:
            if address_id is None:
                attrs["address"] = None
            else:
                request = self.context.get("request")
                address = addresses_owned_by(getattr(request, "user", None)).filter(
                    pk=address_id
                ).first()
                if not address:
                    raise serializers.ValidationError({"address_id": "Address not found."})
                attrs["address"] = address
        elif address_data is not serializers.empty:
            if isinstance(address_data, dict) and (
                "street1" in address_data or "zip_code" in address_data or "attention" in address_data
            ):
                attrs["address"] = map_address_payload(address_data)
            else:
                attrs["address"] = address_data

        return attrs

    def _upsert_address(self, customer_address, address_value):
        if address_value is serializers.empty:
            return

        if address_value is None:
            customer_address.address = None
            return

        if isinstance(address_value, Address):
            customer_address.address = address_value
            return

        if customer_address.address_id:
            for field, value in address_value.items():
                setattr(customer_address.address, field, value)
            customer_address.address.save()
        else:
            customer_address.address = Address.objects.create(**address_value)

    def create(self, validated_data):
        customer_id = validated_data.pop("customer_id")
        address_value = validated_data.pop("address", serializers.empty)
        customer_address = CustomerAddress.objects.create(
            customer_id=customer_id,
            **validated_data,
        )
        self._upsert_address(customer_address, address_value)
        customer_address.save()
        return customer_address

    def update(self, instance, validated_data):
        validated_data.pop("customer_id", None)
        address_value = validated_data.pop("address", serializers.empty)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        self._upsert_address(instance, address_value)
        instance.save()
        return instance


class CustomerPaymentSerializer(serializers.ModelSerializer):
    customer_payment_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = CustomerPayment
        fields = (
            "customer_payment_id",
            "organization_id",
            "customer_id",
            "payment_number",
            "payment_date",
            "amount",
            "payment_mode_id",
            "bank_account_id",
            "reference_number",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CustomerPaymentWriteSerializer(serializers.ModelSerializer):
    customer_id = serializers.UUIDField()
    organization_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = CustomerPayment
        fields = (
            "organization_id",
            "customer_id",
            "payment_number",
            "payment_date",
            "amount",
            "payment_mode_id",
            "bank_account_id",
            "reference_number",
        )

    def validate_payment_number(self, value):
        return value.strip()

    def validate_customer_id(self, value):
        if not Customer.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Customer not found.")
        return value

    def validate(self, attrs):
        customer_id = attrs.get("customer_id")
        attrs.pop("organization_id", None)
        organization_id = None
        payment_number = attrs.get("payment_number")

        if self.instance:
            organization_id = self.instance.organization_id
            payment_number = payment_number or self.instance.payment_number
        elif customer_id:
            organization_id = Customer.objects.get(pk=customer_id).organization_id

        if organization_id and payment_number:
            queryset = CustomerPayment.objects.filter(
                organization_id=organization_id,
                payment_number=payment_number,
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {"payment_number": "Payment number already exists for this organization."}
                )

        return attrs

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        customer_id = validated_data.pop("customer_id")
        customer = Customer.objects.get(pk=customer_id)
        return CustomerPayment.objects.create(
            organization=customer.organization,
            customer=customer,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("customer_id", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
