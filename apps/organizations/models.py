import uuid

from django.conf import settings
from django.db import models

from apps.accounts.countries import get_currency_for_country
from apps.accounts.models import TimeStampedModel


class Organization(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class Industry(models.TextChoices):
        CONSTRUCTION = "construction", "Construction"
        MANUFACTURING = "manufacturing", "Manufacturing"
        RETAIL = "retail", "Retail"
        IT_SOFTWARE = "it_software", "IT / Software"
        HEALTHCARE = "healthcare", "Healthcare"
        EDUCATION = "education", "Education"
        CONSULTING = "consulting", "Consulting"
        HOSPITALITY = "hospitality", "Hospitality"
        REAL_ESTATE = "real_estate", "Real Estate"
        TRANSPORTATION = "transportation", "Transportation"
        AGRICULTURE = "agriculture", "Agriculture"
        FINANCE = "finance", "Finance"
        OTHER = "other", "Other"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        HINDI = "hi", "Hindi"

    name = models.CharField(max_length=255)
    industry = models.CharField(
        max_length=30,
        choices=Industry.choices,
        blank=True,
    )
    country = models.CharField(max_length=2)
    state = models.CharField(max_length=100, blank=True)
    currency = models.CharField(max_length=3)
    language = models.CharField(
        max_length=10,
        choices=Language.choices,
        default=Language.ENGLISH,
    )
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    is_gst_registered = models.BooleanField(default=False)
    gstin = models.CharField(max_length=15, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    is_setup_complete = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_organizations",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.currency:
            self.currency = get_currency_for_country(self.country) or "INR"
        super().save(*args, **kwargs)
