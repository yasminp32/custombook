import uuid

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization


class BankAccount(TimeStampedModel):
    class AccountType(models.TextChoices):
        BANK = "bank", "Bank"
        CREDIT_CARD = "credit_card", "Credit Card"
        CASH = "cash", "Cash"
        UNDEPOSITED_FUNDS = "undeposited_funds", "Undeposited Funds"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="bank_accounts",
        null=True,
        blank=True,
    )
    account_type = models.CharField(
        max_length=30,
        choices=AccountType.choices,
        default=AccountType.BANK,
    )
    name = models.CharField(max_length=200)
    account_code = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, default="INR")
    account_number = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    description = models.CharField(max_length=500, blank=True)
    is_primary = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    books_balance = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )
    bank_balance = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bank_accounts",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "bank_accounts"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_org_bank_account_name",
            ),
            models.UniqueConstraint(
                fields=["organization", "account_code"],
                condition=~models.Q(account_code=""),
                name="unique_org_bank_account_code",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_cash_like(self):
        return self.account_type in (
            self.AccountType.CASH,
            self.AccountType.UNDEPOSITED_FUNDS,
        )

    @property
    def icon(self):
        return {
            self.AccountType.BANK: "bank",
            self.AccountType.CREDIT_CARD: "credit_card",
            self.AccountType.CASH: "cash",
            self.AccountType.UNDEPOSITED_FUNDS: "dollar",
        }.get(self.account_type, "bank")


class BankTransaction(TimeStampedModel):
    class TransactionType(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="bank_transactions",
        null=True,
        blank=True,
    )
    account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_date = models.DateField()
    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
        default=TransactionType.CREDIT,
    )
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    description = models.CharField(max_length=255, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "bank_transactions"
        ordering = ["-transaction_date", "-created_at"]

    def __str__(self):
        return f"{self.account_id}:{self.transaction_date}:{self.amount}"

    @property
    def signed_amount(self):
        amount = self.amount or 0
        if self.transaction_type == self.TransactionType.DEBIT:
            return -amount
        return amount
