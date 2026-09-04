import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization


class PaymentTerm(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="payment_terms",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=50, blank=True)
    due_days = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "payment_terms"
        ordering = ["due_days", "name"]

    def __str__(self):
        return self.name or str(self.id)
