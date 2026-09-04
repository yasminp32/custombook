import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.users.models import User
from apps.vendors.models import Vendor


class Item(TimeStampedModel):
    class ItemType(models.TextChoices):
        GOODS = "goods", "Goods"
        SERVICE = "service", "Service"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    class ValuationMethod(models.TextChoices):
        FIFO = "fifo", "FIFO (First In First Out)"
        LIFO = "lifo", "LIFO (Last In First Out)"
        WAC = "wac", "Weighted Average Cost"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="items",
        null=True,
        blank=True,
    )
    item_type = models.CharField(
        max_length=20,
        choices=ItemType.choices,
        default=ItemType.GOODS,
    )
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    image = models.ImageField(upload_to="items/", blank=True, null=True)
    is_excise_product = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        blank=True,
    )
    synced_with_crm = models.BooleanField(default=False)

    sales_enabled = models.BooleanField(default=True)
    selling_price = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    sales_account = models.CharField(max_length=100, blank=True, default="Sales")
    sales_description = models.TextField(blank=True)
    tax = models.CharField(max_length=100, blank=True)

    purchase_enabled = models.BooleanField(default=True)
    cost_price = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    purchase_account = models.CharField(
        max_length=100,
        blank=True,
        default="Cost of Goods Sold",
    )
    purchase_description = models.TextField(blank=True)
    preferred_vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        related_name="preferred_items",
        null=True,
        blank=True,
    )

    track_inventory = models.BooleanField(default=False)
    inventory_account = models.CharField(
        max_length=100,
        blank=True,
        default="Inventory Asset",
    )
    opening_stock = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    rate_per_unit = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    valuation_method = models.CharField(
        max_length=20,
        choices=ValuationMethod.choices,
        blank=True,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_items",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "items"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "sku"],
                condition=~models.Q(sku=""),
                name="unique_org_item_sku",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def margin(self):
        selling = self.selling_price or 0
        cost = self.cost_price or 0
        return selling - cost
