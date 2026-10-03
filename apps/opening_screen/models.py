import uuid

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.opening_screen.constants import DEFAULT_SCREEN, SCREEN_CODES


class OpeningScreen(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="opening_screen",
    )
    screen = models.CharField(
        max_length=30,
        choices=[(code, label) for code, label in SCREEN_CODES.items()],
        default=DEFAULT_SCREEN,
    )

    class Meta:
        db_table = "opening_screens"

    def __str__(self):
        return f"{self.user_id}:{self.screen}"
