import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.customers.models import Customer
from apps.items.models import Item
from apps.organizations.models import Organization


class Quote(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        SENT = "sent", "SENT"
        ACCEPTED = "accepted", "ACCEPTED"
        DECLINED = "declined", "DECLINED"
        EXPIRED = "expired", "EXPIRED"
        CONVERTED = "converted", "CONVERTED"

    class TaxType(models.TextChoices):
        EXCLUSIVE = "exclusive", "Exclusive"
        INCLUSIVE = "inclusive", "Inclusive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="quotes",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="quotes",
        null=True,
        blank=True,
    )
    quote_number = models.CharField(max_length=30)
    reference_number = models.CharField(max_length=50, blank=True)
    quote_date = models.DateField(default=date.today)
    expiry_date = models.DateField(null=True, blank=True)
    salesperson_id = models.UUIDField(null=True, blank=True)
    salesperson_name = models.CharField(max_length=200, blank=True)
    project_id = models.UUIDField(null=True, blank=True)
    project_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    tax_type = models.CharField(
        max_length=20,
        choices=TaxType.choices,
        default=TaxType.EXCLUSIVE,
        blank=True,
    )
    customer_notes = models.TextField(
        blank=True,
        default="Looking forward for your business.",
    )
    terms_and_conditions = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    total_amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )
    currency = models.CharField(max_length=3, blank=True, default="INR")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_quotes",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "quotes"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "quote_number"],
                name="unique_org_quote_number",
            ),
        ]

    def __str__(self):
        return self.quote_number


class QuoteLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        related_name="quote_lines",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=19, decimal_places=4, default=1)
    rate = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    tax = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "quote_lines"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name or str(self.id)
