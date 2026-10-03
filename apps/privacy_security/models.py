import uuid

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.privacy_security.constants import AUTO_LOCK_OPTIONS


class PrivacySecurity(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="privacy_security",
    )
    enable_app_lock = models.BooleanField(default=False)
    biometric_unlock = models.BooleanField(default=True)
    lock_on_app_exit = models.BooleanField(default=True)
    auto_lock_after = models.CharField(max_length=20, choices=AUTO_LOCK_OPTIONS, default="immediately")
    hide_amounts_on_dashboard = models.BooleanField(default=True)
    cache_cleared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "privacy_security"

    def __str__(self):
        return str(self.user_id)
