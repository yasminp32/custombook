import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.customers.models import Customer
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.quotes.models import Quote


class SalesOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        CONFIRMED = "confirmed", "CONFIRMED"
        INVOICED = "invoiced", "INVOICED"
        CANCELLED = "cancelled", "CANCELLED"

    class TaxType(models.TextChoices):
        EXCLUSIVE = "exclusive", "Exclusive"
        INCLUSIVE = "inclusive", "Inclusive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="sales_orders",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales_orders",
        null=True,
        blank=True,
    )
    quote = models.ForeignKey(
        Quote,
        on_delete=models.SET_NULL,
        related_name="sales_orders",
        null=True,
        blank=True,
    )
    sales_order_number = models.CharField(max_length=30)
    reference_number = models.CharField(max_length=50, blank=True)
    order_date = models.DateField(default=date.today)
    expected_shipment_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=40, blank=True)
    delivery_method = models.CharField(max_length=100, blank=True)
    salesperson_id = models.UUIDField(null=True, blank=True)
    salesperson_name = models.CharField(max_length=200, blank=True)
    project_id = models.UUIDField(null=True, blank=True)
    project_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    tax_type = models.CharField(
        max_length=20,
        choices=TaxType.choices,
        default=TaxType.EXCLUSIVE,
        blank=True,
    )
    customer_notes = models.TextField(
        blank=True,
        default="Looking forward for your business.",
    )
    terms_and_conditions = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    invoiced_at = models.DateTimeField(null=True, blank=True)
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
        related_name="created_sales_orders",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "sales_orders"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "sales_order_number"],
                name="unique_org_sales_order_number",
            ),
        ]

    def __str__(self):
        return self.sales_order_number


class SalesOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        related_name="sales_order_lines",
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
        db_table = "sales_order_lines"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name or str(self.id)
