import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization


class OrganizationPaymentGateway(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="payment_gateways",
    )
    gateway_code = models.CharField(max_length=30)
    is_setup = models.BooleanField(default=True)

    class Meta:
        db_table = "organization_payment_gateways"
        ordering = ["gateway_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "gateway_code"],
                name="unique_organization_payment_gateway",
            ),
        ]

    def __str__(self):
        return f"{self.organization_id}:{self.gateway_code}"
