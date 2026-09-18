import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.projects.models import Project


class TimeEntry(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="time_entries",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="time_entries",
        null=True,
        blank=True,
    )
    task_name = models.CharField(max_length=200)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="time_entries",
        null=True,
        blank=True,
    )
    log_date = models.DateField(default=date.today)
    hours = models.PositiveIntegerField(default=0)
    minutes = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(default=0)
    is_billable = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_time_entries",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "time_entries"
        ordering = ["-created_at"]

    def __str__(self):
        return self.task_name

    def refresh_duration_minutes(self):
        self.duration_minutes = (self.hours or 0) * 60 + (self.minutes or 0)

    def save(self, *args, **kwargs):
        self.refresh_duration_minutes()
        super().save(*args, **kwargs)
