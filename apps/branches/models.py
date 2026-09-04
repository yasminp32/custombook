import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.organizations.models import Organization


class Address(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attention = models.CharField(max_length=200, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=2, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=30, blank=True)
    phone_country_code = models.CharField(max_length=8, blank=True, default="+91")
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name_plural = "addresses"

    def __str__(self):
        return self.address_line1 or str(self.id)


class Branch(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="branches",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100, blank=True)
    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        related_name="branches",
        null=True,
        blank=True,
    )
    is_primary = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        blank=True,
    )

    class Meta:
        ordering = ["-is_primary", "name"]
        verbose_name_plural = "branches"

    def __str__(self):
        return self.name or str(self.id)
