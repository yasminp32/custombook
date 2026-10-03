import random
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
        FOOD_GROCERIES = "food_groceries", "Food, Groceries & Beverages"
        TECHNOLOGY = "technology", "Technology"
        SERVICES = "services", "Services"
        OTHER = "other", "Other"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        ARABIC = "ar", "Arabic"
        HINDI = "hi", "Hindi"
        FRENCH = "fr", "French"
        SPANISH = "es", "Spanish"

    class FiscalYear(models.TextChoices):
        JANUARY_DECEMBER = "january_december", "January - December"
        APRIL_MARCH = "april_march", "April - March"
        JULY_JUNE = "july_june", "July - June"
        OCTOBER_SEPTEMBER = "october_september", "October - September"

    class DateFormat(models.TextChoices):
        DD_MMM_YYYY = "dd_mmm_yyyy", "dd MMM yyyy"
        MM_DD_YYYY = "mm_dd_yyyy", "MM/dd/yyyy"
        DD_MM_YYYY = "dd_mm_yyyy", "dd/MM/yyyy"
        YYYY_MM_DD = "yyyy_mm_dd", "yyyy-MM-dd"

    name = models.CharField(max_length=255)
    organization_number = models.PositiveIntegerField(unique=True, null=True, blank=True)
    portal_name = models.CharField(max_length=50, unique=True, null=True, blank=True)
    logo = models.ImageField(upload_to="organizations/logos/", blank=True, null=True)
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
    phone = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    website = models.CharField(max_length=255, blank=True)
    update_address_in_previous_transactions = models.BooleanField(default=False)
    use_payment_stub_address = models.BooleanField(default=False)
    payment_stub_address_line1 = models.CharField(max_length=255, blank=True)
    payment_stub_address_line2 = models.CharField(max_length=255, blank=True)
    payment_stub_city = models.CharField(max_length=100, blank=True)
    payment_stub_state = models.CharField(max_length=100, blank=True)
    payment_stub_postal_code = models.CharField(max_length=20, blank=True)
    fiscal_year = models.CharField(
        max_length=30,
        choices=FiscalYear.choices,
        default=FiscalYear.JANUARY_DECEMBER,
    )
    date_format = models.CharField(
        max_length=20,
        choices=DateFormat.choices,
        default=DateFormat.DD_MMM_YYYY,
    )
    company_id = models.CharField(max_length=50, blank=True)
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
        if not self.organization_number:
            self.organization_number = next_organization_number()
        if not self.portal_name:
            self.portal_name = f"store{self.organization_number}"
        super().save(*args, **kwargs)


def next_organization_number():
    for _ in range(20):
        number = random.randint(100000000, 999999999)
        if not Organization.objects.filter(organization_number=number).exists():
            return number
    raise RuntimeError("Could not allocate an organization number.")
