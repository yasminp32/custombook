import uuid

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.image_upload.constants import DEFAULT_RESOLUTION, RESOLUTION_CODES


class ImageUploadResolution(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="image_upload_resolution",
    )
    resolution = models.CharField(
        max_length=20,
        choices=[(code, code) for code in RESOLUTION_CODES],
        default=DEFAULT_RESOLUTION,
    )

    class Meta:
        db_table = "image_upload_resolutions"

    def __str__(self):
        return f"{self.user_id}:{self.resolution}"
