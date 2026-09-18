import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.organizations.models import Organization


class CreditNote(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        OPEN = "open", "OPEN"
        CLOSED = "closed", "CLOSED"
        VOID = "void", "VOID"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="credit_notes",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="credit_notes",
        null=True,
        blank=True,
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        related_name="credit_notes",
        null=True,
        blank=True,
    )
    credit_note_number = models.CharField(max_length=30)
    reference_number = models.CharField(max_length=50, blank=True)
    credit_note_date = models.DateField(default=date.today)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_credit_notes",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "credit_notes"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "credit_note_number"],
                name="unique_org_credit_note_number",
            ),
        ]

    def __str__(self):
        return self.credit_note_number
