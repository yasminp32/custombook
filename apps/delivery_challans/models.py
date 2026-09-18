import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.customers.models import Customer
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.sales_orders.models import SalesOrder


class DeliveryChallan(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        DELIVERED = "delivered", "DELIVERED"
        RETURNED = "returned", "RETURNED"
        CANCELLED = "cancelled", "CANCELLED"

    class ChallanType(models.TextChoices):
        JOB_WORK = "job_work", "Job Work"
        SUPPLY_ON_APPROVAL = "supply_on_approval", "Supply on Approval"
        SUPPLY_OF_LIQUID_GAS = "supply_of_liquid_gas", "Supply of Liquid Gas"
        OTHERS = "others", "Others"

    class TaxType(models.TextChoices):
        EXCLUSIVE = "exclusive", "Exclusive"
        INCLUSIVE = "inclusive", "Inclusive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="delivery_challans",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="delivery_challans",
        null=True,
        blank=True,
    )
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.SET_NULL,
        related_name="delivery_challans",
        null=True,
        blank=True,
    )
    challan_number = models.CharField(max_length=30)
    reference_number = models.CharField(max_length=50, blank=True)
    challan_date = models.DateField(default=date.today)
    challan_type = models.CharField(
        max_length=40,
        choices=ChallanType.choices,
        default=ChallanType.JOB_WORK,
        blank=True,
    )
    tax_type = models.CharField(
        max_length=20,
        choices=TaxType.choices,
        default=TaxType.EXCLUSIVE,
        blank=True,
    )
    customer_notes = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    total_amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )
    currency = models.CharField(max_length=3, blank=True, default="INR")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_delivery_challans",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "delivery_challans"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "challan_number"],
                name="unique_org_challan_number",
            ),
        ]

    def __str__(self):
        return self.challan_number


class DeliveryChallanLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_challan = models.ForeignKey(
        DeliveryChallan,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        related_name="delivery_challan_lines",
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
        db_table = "delivery_challan_lines"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name or str(self.id)
