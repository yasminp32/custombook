import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.preferences import constants


def default_enabled_modules():
    return list(constants.DEFAULT_ENABLED_MODULES)


class Preference(TimeStampedModel):
    class DiscountType(models.TextChoices):
        NONE = "none", "I don't give discounts"
        LINE_ITEM = "line_item", "At Line Item Level"
        INVOICE = "invoice", "At Invoice Level"

    class TaxType(models.TextChoices):
        INCLUSIVE = "tax_inclusive", "Tax Inclusive"
        EXCLUSIVE = "tax_exclusive", "Tax Exclusive"
        BOTH = "both", "Tax Inclusive or Tax Exclusive"

    class Rounding(models.TextChoices):
        NONE = "none", "No Rounding"
        NEAREST_WHOLE = "nearest_whole", "Round off the total to the nearest whole number"

    class CustomerType(models.TextChoices):
        BUSINESS = "business", "Business"
        INDIVIDUAL = "individual", "Individual"

    class MileageUnit(models.TextChoices):
        KILOMETER = "kilometer", "Kilometer"
        MILE = "mile", "Mile"

    class MileageCategory(models.TextChoices):
        FUEL_MILEAGE = "fuel_mileage", "Fuel/Mileage Expenses"
        TRAVEL = "travel", "Travel Expenses"
        VEHICLE = "vehicle", "Vehicle Expenses"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="preference",
    )

    # General
    enabled_modules = models.JSONField(default=default_enabled_modules, blank=True)
    attach_pdf_in_email = models.BooleanField(default=True)
    encrypt_pdf = models.BooleanField(default=False)
    discount_type = models.CharField(
        max_length=20, choices=DiscountType.choices, default=DiscountType.LINE_ITEM
    )
    tax_type = models.CharField(max_length=20, choices=TaxType.choices, default=TaxType.BOTH)
    rounding = models.CharField(max_length=20, choices=Rounding.choices, default=Rounding.NONE)
    enable_salesperson_field = models.BooleanField(default=True)
    organization_address_format = models.TextField(
        default=constants.DEFAULT_ORGANIZATION_ADDRESS_FORMAT, blank=True
    )

    # Customers and vendors
    default_customer_type = models.CharField(
        max_length=20, choices=CustomerType.choices, default=CustomerType.BUSINESS
    )
    allow_duplicate_display_name = models.BooleanField(default=True)
    enable_credit_limit = models.BooleanField(default=False)
    billing_address_format = models.TextField(
        default=constants.DEFAULT_BILLING_ADDRESS_FORMAT, blank=True
    )
    shipping_address_format = models.TextField(
        default=constants.DEFAULT_SHIPPING_ADDRESS_FORMAT, blank=True
    )

    # Items
    enable_inventory = models.BooleanField(default=False)
    inventory_start_date = models.DateField(null=True, blank=True)
    notify_below_reorder_point = models.BooleanField(default=False)

    # Quotes
    quote_auto_generate_number = models.BooleanField(default=True)
    quote_prefix = models.CharField(max_length=20, default="QT-", blank=True)
    quote_next_number = models.PositiveIntegerField(default=1)
    quote_notes = models.TextField(default=constants.DEFAULT_QUOTE_NOTES, blank=True)
    quote_terms = models.TextField(blank=True)
    quote_auto_convert_to_invoice = models.BooleanField(default=False)
    quote_prefill_country_code = models.BooleanField(default=False)
    quote_default_country_code = models.CharField(max_length=8, blank=True)

    # Invoices
    invoice_auto_generate_number = models.BooleanField(default=True)
    invoice_prefix = models.CharField(max_length=20, default="INV-", blank=True)
    invoice_next_number = models.PositiveIntegerField(default=1)
    invoice_notes = models.TextField(default=constants.DEFAULT_INVOICE_NOTES, blank=True)
    invoice_terms = models.TextField(blank=True)
    invoice_allow_edit_sent = models.BooleanField(default=True)
    invoice_discount_before_tax = models.BooleanField(default=True)
    invoice_show_expense_receipts_in_pdf = models.BooleanField(default=False)

    # Expenses
    mileage_unit = models.CharField(
        max_length=20, choices=MileageUnit.choices, default=MileageUnit.KILOMETER
    )
    mileage_category = models.CharField(
        max_length=20, choices=MileageCategory.choices, default=MileageCategory.FUEL_MILEAGE
    )

    # Vendor portal
    vendor_portal_notify_activity = models.BooleanField(default=True)
    vendor_portal_notify_vendors_on_comment = models.BooleanField(default=True)
    vendor_portal_allow_contact_update = models.BooleanField(default=False)
    vendor_portal_allow_po_accept_reject = models.BooleanField(default=False)
    vendor_portal_allow_document_upload = models.BooleanField(default=False)

    class Meta:
        db_table = "preferences"

    def __str__(self):
        return f"Preferences for {self.organization_id}"


class CustomField(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="custom_fields",
    )
    entity = models.CharField(max_length=30, choices=constants.CUSTOM_FIELD_ENTITIES)
    label = models.CharField(max_length=100)
    data_type = models.CharField(
        max_length=20, choices=constants.CUSTOM_FIELD_DATA_TYPES, default="text"
    )
    options = models.JSONField(default=list, blank=True)
    is_mandatory = models.BooleanField(default=False)
    show_in_pdf = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "preference_custom_fields"
        ordering = ["entity", "sort_order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "entity", "label"],
                name="unique_custom_field_label_per_entity",
            ),
        ]

    def __str__(self):
        return f"{self.entity}:{self.label}"


class MileageRate(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="mileage_rates",
    )
    start_date = models.DateField()
    rate = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "preference_mileage_rates"
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "start_date"],
                name="unique_mileage_rate_start_date",
            ),
        ]

    def __str__(self):
        return f"{self.start_date}: {self.rate}"
