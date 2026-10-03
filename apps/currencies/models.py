import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.currencies import constants
from apps.organizations.models import Organization


class Currency(TimeStampedModel):
    class NumberFormat(models.TextChoices):
        COMMA_DOT = "comma_dot", "1,234,567.89"
        DOT_COMMA = "dot_comma", "1.234.567,89"
        SPACE_DOT = "space_dot", "1 234 567.89"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="currencies",
    )
    code = models.CharField(max_length=3)
    symbol = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    number_format = models.CharField(
        max_length=20,
        choices=NumberFormat.choices,
        default=NumberFormat.COMMA_DOT,
    )

    class Meta:
        db_table = "currencies"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_organization_currency_code",
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def is_base(self):
        return bool(self.organization_id) and self.code == (self.organization.currency or "").upper()

    def format(self, value):
        return constants.format_amount(value, self.decimal_places, self.number_format)

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)
