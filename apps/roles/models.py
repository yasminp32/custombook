import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel


class Role(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role_name = models.CharField(max_length=50)
    role_code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=False)

    class Meta:
        db_table = "roles"
        ordering = ["role_name"]

    def __str__(self):
        return self.role_name
