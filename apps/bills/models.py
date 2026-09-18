import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.purchase_orders.models import PurchaseOrder
from apps.vendors.models import Vendor

DEFAULT_DUE_DAYS = 15


class Bill(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        OPEN = "open", "OPEN"
        PAID = "paid", "PAID"
        PARTIALLY_PAID = "partially_paid", "PARTIALLY PAID"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="bills",
        null=True,
        blank=True,
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="bills",
        null=True,
        blank=True,
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        related_name="bills",
        null=True,
        blank=True,
    )
    bill_number = models.CharField(max_length=30)
    bill_date = models.DateField(default=date.today)
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    amount_paid = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_bills",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "bills"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "bill_number"],
                name="unique_org_bill_number",
            ),
        ]

    def __str__(self):
        return self.bill_number

    def is_overdue(self):
        if self.status != self.Status.OPEN:
            return False
        return bool(self.due_date and self.due_date < date.today())

    def effective_status(self):
        if self.is_overdue():
            return "overdue"
        return self.status

    def display_status_label(self):
        if self.is_overdue():
            return "OVERDUE"
        return self.get_status_display()
