import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.vendors.models import Vendor


class PaymentMade(TimeStampedModel):
    class PaymentMode(models.TextChoices):
        CASH = "cash", "Cash"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        CARD = "card", "Card"
        CHEQUE = "cheque", "Cheque"
        UPI = "upi", "UPI"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="payments_made",
        null=True,
        blank=True,
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="payments_made",
        null=True,
        blank=True,
    )
    payment_number = models.CharField(max_length=30)
    payment_date = models.DateField(default=date.today)
    payment_mode = models.CharField(
        max_length=20,
        choices=PaymentMode.choices,
        default=PaymentMode.BANK_TRANSFER,
        blank=True,
    )
    reference_number = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_payments_made",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "payments_made"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "payment_number"],
                name="unique_org_payment_made_number",
            ),
        ]

    def __str__(self):
        return self.payment_number
