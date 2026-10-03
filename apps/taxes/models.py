import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization


class TaxSettings(TimeStampedModel):
    class ReportingPeriod(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        CUSTOM = "custom", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="tax_settings",
    )
    is_vat_registered = models.BooleanField(default=False)
    tax_registration_number = models.CharField(max_length=20, blank=True)
    enable_international_trade = models.BooleanField(default=False)
    vat_registration_date = models.DateField(null=True, blank=True)
    first_tax_return_from = models.DateField(null=True, blank=True)
    reporting_period = models.CharField(
        max_length=20,
        choices=ReportingPeriod.choices,
        default=ReportingPeriod.MONTHLY,
    )
    profit_margin_scheme = models.BooleanField(default=False)

    class Meta:
        db_table = "tax_settings"

    def __str__(self):
        return f"Tax settings for {self.organization_id}"


class TaxRate(TimeStampedModel):
    class TaxType(models.TextChoices):
        TAX = "tax", "Tax"
        GROUP = "group", "Tax Group"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="tax_rates",
    )
    name = models.CharField(max_length=100)
    rate = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    tax_type = models.CharField(max_length=10, choices=TaxType.choices, default=TaxType.TAX)
    is_default = models.BooleanField(default=False)
    members = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="groups",
    )

    class Meta:
        db_table = "tax_rates"
        ordering = ["-is_default", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_organization_tax_name",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def rate_label(self):
        return f"{self.rate:.1f}%"

    @property
    def display_name(self):
        if self.is_default:
            return f"{self.name} - Default Tax"
        return self.name
