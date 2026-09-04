import uuid

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.items.models import Item
from apps.organizations.models import Organization


class InventoryAdjustment(TimeStampedModel):
    class AdjustmentType(models.TextChoices):
        QUANTITY = "quantity", "By Quantity"
        VALUE = "value", "By Value"

    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        COMPLETED = "completed", "COMPLETED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="inventory_adjustments",
        null=True,
        blank=True,
    )
    adjustment_type = models.CharField(
        max_length=20,
        choices=AdjustmentType.choices,
        default=AdjustmentType.QUANTITY,
    )
    reason = models.CharField(max_length=200)
    date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    reference_number = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    account = models.CharField(max_length=100, blank=True, default="Inventory Asset")
    adjusted_by_name = models.CharField(max_length=200, blank=True)
    quantity_change = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )
    adjustment_value = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )
    stock_applied = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="inventory_adjustments",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "inventory_adjustments"
        ordering = ["-created_at"]

    def __str__(self):
        return self.reason


class InventoryAdjustmentLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adjustment = models.ForeignKey(
        InventoryAdjustment,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="inventory_adjustment_lines",
        null=True,
        blank=True,
    )
    quantity_adjusted = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )
    rate = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    value = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )

    class Meta:
        db_table = "inventory_adjustment_lines"
        ordering = ["id"]

    def __str__(self):
        return f"{self.adjustment_id}:{self.item_id}"
