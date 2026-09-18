import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.vendors.models import Vendor


DEFAULT_EXPENSE_CATEGORIES = (
    ("fuel_mileage", "Fuel/Mileage"),
    ("office_supplies", "Office Supplies"),
    ("travel", "Travel"),
    ("meals_entertainment", "Meals & Entertainment"),
)


class ExpenseCategory(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="expense_categories",
        null=True,
        blank=True,
    )
    key = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "expense_categories"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "key"],
                name="unique_org_expense_category_key",
            ),
        ]

    def __str__(self):
        return self.name


class Expense(TimeStampedModel):
    class Status(models.TextChoices):
        UNBILLED = "unbilled", "UNBILLED"
        BILLED = "billed", "BILLED"
        REIMBURSED = "reimbursed", "REIMBURSED"
        NON_BILLABLE = "non_billable", "NON-BILLABLE"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="expenses",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
        null=True,
        blank=True,
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        related_name="expenses",
        null=True,
        blank=True,
    )
    expense_date = models.DateField(default=date.today)
    reference_number = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNBILLED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_expenses",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "expenses"
        ordering = ["-created_at"]

    def __str__(self):
        return self.category.name if self.category else str(self.id)
