import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.pdf_templates.constants import DOCUMENT_TYPES, THEMES


class PdfTemplate(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="pdf_templates",
    )
    document_type = models.CharField(
        max_length=30,
        choices=[(code, label) for code, label, _title, _number in DOCUMENT_TYPES],
    )
    name = models.CharField(max_length=100)
    theme = models.CharField(
        max_length=20,
        choices=[(code, label) for code, label, _color in THEMES],
        default="blue",
    )
    is_default = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=40, blank=True)
    ifsc_swift_code = models.CharField(max_length=20, blank=True)
    branch = models.CharField(max_length=100, blank=True)
    signatory_name = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "pdf_templates"
        ordering = ["-is_default", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "document_type", "name"],
                name="unique_pdf_template_name",
            ),
        ]

    def __str__(self):
        return f"{self.document_type}: {self.name}"

    @property
    def bank_details_set(self):
        return any([self.bank_name, self.account_number, self.ifsc_swift_code, self.branch])
