import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization


class ManualJournal(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "DRAFT"
        PUBLISHED = "published", "PUBLISHED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="manual_journals",
        null=True,
        blank=True,
    )
    journal_number = models.CharField(max_length=30)
    reference_number = models.CharField(max_length=50, blank=True)
    journal_date = models.DateField(default=date.today)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_manual_journals",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "manual_journals"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "journal_number"],
                name="unique_org_manual_journal_number",
            ),
        ]

    def __str__(self):
        return self.journal_number
