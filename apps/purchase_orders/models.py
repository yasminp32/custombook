import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.vendors.models import Vendor


class PurchaseOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        ISSUED = "issued", "ISSUED"
        BILLED = "billed", "BILLED"
        CANCELLED = "cancelled", "CANCELLED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="purchase_orders",
        null=True,
        blank=True,
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        null=True,
        blank=True,
    )
    purchase_order_number = models.CharField(max_length=30)
    reference_number = models.CharField(max_length=50, blank=True)
    order_date = models.DateField(default=date.today)
    expected_delivery_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    billed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_purchase_orders",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "purchase_orders"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "purchase_order_number"],
                name="unique_org_purchase_order_number",
            ),
        ]

    def __str__(self):
        return self.purchase_order_number
