import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.sender_emails.constants import DELIVERY_METHODS


class SenderEmailPreference(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="sender_email_preference",
    )
    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_METHODS,
        default="system",
    )

    class Meta:
        db_table = "sender_email_preferences"

    def __str__(self):
        return f"{self.organization_id}:{self.delivery_method}"


class SenderEmail(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="sender_emails",
    )
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "sender_emails"
        ordering = ["-is_primary", "name", "email"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                name="unique_organization_sender_email",
            ),
        ]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)
