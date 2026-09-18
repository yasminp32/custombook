import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.projects.models import Project

DEFAULT_TASKS = (
    "Homepage layout",
    "API integration",
    "Design review",
    "Keyword research",
    "Bug fixing",
)


class TimerSession(TimeStampedModel):
    class Status(models.TextChoices):
        PAUSED = "paused", "Paused"
        RUNNING = "running", "Running"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="timer_sessions",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="timer_sessions",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        related_name="timer_sessions",
        null=True,
        blank=True,
    )
    task_name = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PAUSED,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    accumulated_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "timer_sessions"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_org_user_timer",
            ),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.status}"

    def elapsed_seconds(self):
        total = int(self.accumulated_seconds or 0)
        if self.status == self.Status.RUNNING and self.started_at:
            total += int((timezone.now() - self.started_at).total_seconds())
        return max(total, 0)

    def elapsed_display(self):
        total = self.elapsed_seconds()
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def to_hours_minutes(self):
        total = self.elapsed_seconds()
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if seconds >= 30:
            minutes += 1
        if minutes >= 60:
            hours += 1
            minutes = 0
        return hours, minutes
