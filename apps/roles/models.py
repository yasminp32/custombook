import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization


class Role(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="roles",
        null=True,
        blank=True,
    )
    role_name = models.CharField(max_length=50)
    role_code = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=False)

    class Meta:
        db_table = "roles"
        ordering = ["role_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "role_code"],
                name="unique_organization_role_code",
            ),
        ]

    def __str__(self):
        return self.role_name
