import uuid
from calendar import monthrange
from datetime import date, timedelta

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.customers.models import Customer
from apps.organizations.models import Organization


def add_months(start, months):
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


class RecurringInvoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        ACTIVE = "active", "ACTIVE"
        STOPPED = "stopped", "STOPPED"
        EXPIRED = "expired", "EXPIRED"

    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        YEARLY = "yearly", "Yearly"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="recurring_invoices",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="recurring_invoices",
        null=True,
        blank=True,
    )
    profile_name = models.CharField(max_length=200)
    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.MONTHLY,
        blank=True,
    )
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(null=True, blank=True)
    next_invoice_date = models.DateField(null=True, blank=True)
    last_invoice_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    stopped_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_recurring_invoices",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "recurring_invoices"
        ordering = ["-created_at"]

    def __str__(self):
        return self.profile_name

    def is_expired(self):
        if self.status == self.Status.EXPIRED:
            return True
        if self.status != self.Status.ACTIVE:
            return False
        return bool(self.end_date and self.end_date < date.today())

    def effective_status(self):
        if self.is_expired() and self.status != self.Status.STOPPED:
            return self.Status.EXPIRED
        return self.status

    def next_date_after(self, from_date):
        from_date = from_date or self.start_date or date.today()
        if self.frequency == self.Frequency.WEEKLY:
            return from_date + timedelta(days=7)
        if self.frequency == self.Frequency.MONTHLY:
            return add_months(from_date, 1)
        if self.frequency == self.Frequency.QUARTERLY:
            return add_months(from_date, 3)
        if self.frequency == self.Frequency.YEARLY:
            return add_months(from_date, 12)
        return add_months(from_date, 1)


class RecurringInvoiceActivity(TimeStampedModel):
    class ActivityType(models.TextChoices):
        COMMENT = "comment", "Comment"
        HISTORY = "history", "History"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recurring_invoice = models.ForeignKey(
        RecurringInvoice,
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
        related_name="recurring_invoice_activities",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "recurring_invoice_activities"
        ordering = ["-created_at"]

    def __str__(self):
        return self.message[:80]
