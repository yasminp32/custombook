import uuid

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.feedback.constants import CATEGORIES, SUBJECT_MAX_LENGTH


class Feedback(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedback_submissions",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        related_name="feedback_submissions",
        null=True,
        blank=True,
    )
    rating = models.PositiveSmallIntegerField()
    category = models.CharField(max_length=30, choices=CATEGORIES)
    subject = models.CharField(max_length=SUBJECT_MAX_LENGTH)
    message = models.TextField()

    class Meta:
        db_table = "feedback"
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject
