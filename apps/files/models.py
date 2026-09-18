import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization

FILE_TYPE_BY_EXTENSION = {
    ".pdf": "pdf",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    ".bmp": "image",
    ".heic": "image",
    ".xlsx": "spreadsheet",
    ".xls": "spreadsheet",
    ".csv": "spreadsheet",
    ".ods": "spreadsheet",
    ".docx": "document",
    ".doc": "document",
    ".rtf": "document",
    ".odt": "document",
}


class StoredFile(TimeStampedModel):
    class FileType(models.TextChoices):
        PDF = "pdf", "PDF"
        IMAGE = "image", "Image"
        SPREADSHEET = "spreadsheet", "Spreadsheet"
        DOCUMENT = "document", "Document"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="stored_files",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.BigIntegerField(default=0)
    storage_key = models.TextField(blank=True)
    file_type = models.CharField(
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER,
    )
    folder = models.CharField(max_length=50, default="All documents")
    share_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="stored_files",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "files"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @classmethod
    def type_from_name(cls, name):
        extension = Path(name or "").suffix.lower()
        return FILE_TYPE_BY_EXTENSION.get(extension, cls.FileType.OTHER)
