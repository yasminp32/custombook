import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.organizations.models import Organization

ZERO = Decimal("0.00")


class PaymentReceived(TimeStampedModel):
    class PaymentMode(models.TextChoices):
        CASH = "cash", "Cash"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        CARD = "card", "Card"
        CREDIT_CARD = "credit_card", "Credit Card"
        CHEQUE = "cheque", "Cheque"
        UPI = "upi", "UPI"

    class Template(models.TextChoices):
        STANDARD = "standard", "Standard Template"
        ELITE = "elite", "Elite Template"
        CLASSIC = "classic", "Classic Template"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="payments_received",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="payments_received",
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
    amount_applied = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    bank_charges = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    notes = models.TextField(blank=True)
    bank_account_id = models.UUIDField(null=True, blank=True)
    template = models.CharField(
        max_length=20,
        choices=Template.choices,
        default=Template.STANDARD,
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="voided_payments_received",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_payments_received",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "payments_received"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "payment_number"],
                name="unique_org_payment_received_number",
            ),
        ]

    def __str__(self):
        return self.payment_number

    @property
    def unused_amount(self):
        if self.voided_at is not None:
            return ZERO
        remaining = (self.amount or ZERO) - (self.amount_applied or ZERO)
        return remaining if remaining > ZERO else ZERO

    @property
    def is_void(self):
        return self.voided_at is not None

    def is_unapplied(self):
        return self.unused_amount > ZERO

    def application_status(self):
        if self.is_void:
            return "void"
        return "unapplied" if self.is_unapplied() else "applied"


class PaymentReceivedActivity(TimeStampedModel):
    class ActivityType(models.TextChoices):
        COMMENT = "comment", "Comment"
        HISTORY = "history", "History"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        PaymentReceived,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices,
        default=ActivityType.HISTORY,
    )
    message = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="payment_received_activities",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "payment_received_activities"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.payment_id}: {self.message[:40]}"


class PaymentReceivedApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        PaymentReceived,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payment_applications",
    )
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_received_applications"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "invoice"],
                name="unique_payment_invoice_application",
            ),
        ]

    def __str__(self):
        return f"{self.payment_id}:{self.invoice_id}"
