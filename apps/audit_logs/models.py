from django.db import models
from django.utils import timezone

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.users.models import User


class AuditLog(TimeStampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    entity_type = models.CharField(max_length=50, blank=True)
    entity_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=30, blank=True)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-occurred_at", "-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["organization", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.action}:{self.entity_type}:{self.entity_id}"

    def save(self, *args, **kwargs):
        if not self.occurred_at:
            self.occurred_at = timezone.now()
        super().save(*args, **kwargs)
