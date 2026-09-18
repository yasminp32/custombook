import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.customers.models import Customer
from apps.delivery_challans.models import DeliveryChallan
from apps.items.models import Item
from apps.organizations.models import Organization
from apps.sales_orders.models import SalesOrder


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        SENT = "sent", "SENT"
        PAID = "paid", "PAID"
        PARTIALLY_PAID = "partially_paid", "PARTIALLY PAID"
        CANCELLED = "cancelled", "CANCELLED"

    class TaxType(models.TextChoices):
        EXCLUSIVE = "exclusive", "Exclusive"
        INCLUSIVE = "inclusive", "Inclusive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invoices",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices",
        null=True,
        blank=True,
    )
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.SET_NULL,
        related_name="invoices",
        null=True,
        blank=True,
    )
    delivery_challan = models.ForeignKey(
        DeliveryChallan,
        on_delete=models.SET_NULL,
        related_name="invoices",
        null=True,
        blank=True,
    )
    invoice_number = models.CharField(max_length=30)
    order_number = models.CharField(max_length=50, blank=True)
    invoice_date = models.DateField(default=date.today)
    due_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=40, blank=True, default="due_on_receipt")
    place_of_supply = models.CharField(max_length=100, blank=True)
    tax_treatment = models.CharField(max_length=40, blank=True)
    salesperson_id = models.UUIDField(null=True, blank=True)
    salesperson_name = models.CharField(max_length=200, blank=True)
    subject = models.TextField(blank=True)
    tax_type = models.CharField(
        max_length=20,
        choices=TaxType.choices,
        default=TaxType.EXCLUSIVE,
        blank=True,
    )
    customer_notes = models.TextField(blank=True, default="Thanks for your business.")
    terms_and_conditions = models.TextField(blank=True)
    email_recipients = models.JSONField(default=list, blank=True)
    payment_received = models.BooleanField(default=False)
    amount_paid = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_invoices",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "invoices"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "invoice_number"],
                name="unique_org_invoice_number",
            ),
        ]

    def __str__(self):
        return self.invoice_number

    def is_overdue(self):
        if self.status in (
            self.Status.DRAFT,
            self.Status.PAID,
            self.Status.CANCELLED,
        ):
            return False
        return bool(self.due_date and self.due_date < date.today())

    def effective_status(self):
        if self.is_overdue():
            return "overdue"
        return self.status


class InvoiceLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        related_name="invoice_lines",
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
        db_table = "invoice_lines"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name or str(self.id)
