import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.customers.models import Customer
from apps.organizations.models import Organization

ZERO = Decimal("0.00")


class Project(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "ACTIVE"
        ON_HOLD = "on_hold", "ON HOLD"
        COMPLETED = "completed", "COMPLETED"
        CANCELLED = "cancelled", "CANCELLED"

    class BillingMethod(models.TextChoices):
        FIXED_COST = "fixed_cost", "Fixed Cost for Project"
        PROJECT_HOURS = "project_hours", "Based on Project Hours"
        STAFF_HOURS = "staff_hours", "Based on Staff Hours"
        TASK_HOURS = "task_hours", "Based on Task Hours"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="projects",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="projects",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    billing_method = models.CharField(
        max_length=30,
        choices=BillingMethod.choices,
        default=BillingMethod.FIXED_COST,
    )
    rate = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    budget_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    on_hold_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_projects",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "projects"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def computed_amount(self):
        rate = Decimal(self.rate or 0)
        hours = Decimal(self.budget_hours or 0)
        if self.billing_method == self.BillingMethod.FIXED_COST:
            return rate
        return rate * hours
