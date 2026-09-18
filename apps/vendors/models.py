import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.payment_terms.models import PaymentTerm
from apps.users.models import User


class Vendor(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="vendors",
        null=True,
        blank=True,
    )
    display_name = models.CharField(max_length=200, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    payment_term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.SET_NULL,
        related_name="vendors",
        null=True,
        blank=True,
    )
    opening_balance = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        blank=True,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_vendors",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "vendors"
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name or self.company_name or str(self.id)

    @property
    def name(self):
        return self.display_name or self.company_name or ""

    @property
    def payables(self):
        return self.opening_balance or 0


class VendorPayment(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="vendor_payments",
        null=True,
        blank=True,
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True,
    )
    payment_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    payment_mode_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "vendor_payments"
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"{self.vendor_id}:{self.payment_date}:{self.amount}"
