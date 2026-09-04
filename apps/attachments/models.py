import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization


class Attachment(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="attachments",
        null=True,
        blank=True,
    )
    file_name = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    storage_key = models.TextField(blank=True)
    attachable_type = models.CharField(max_length=50, blank=True)
    attachable_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "attachments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["attachable_type", "attachable_id"]),
        ]

    def __str__(self):
        return self.file_name or str(self.id)
