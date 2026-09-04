import uuid

from django.db import models

from apps.accounts.models import TimeStampedModel
from apps.branches.models import Address
from apps.organizations.models import Organization
from apps.users.models import User


class Customer(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    class CustomerType(models.TextChoices):
        BUSINESS = "business", "Business"
        INDIVIDUAL = "individual", "Individual"

    class TaxTreatment(models.TextChoices):
        GST_REGISTERED = "gst_registered", "GST Registered"
        NON_GST_REGISTERED = "non_gst_registered", "Non GST Registered"
        GST_REGISTERED_COMPOSITION = (
            "gst_registered_composition",
            "GST Registered - Composition",
        )
        CONSUMER = "consumer", "Consumer"
        OVERSEAS = "overseas", "Overseas"
        SEZ = "sez", "SEZ"

    class PaymentTerms(models.TextChoices):
        DUE_ON_RECEIPT = "due_on_receipt", "Due on Receipt"
        NET_15 = "net_15", "Net 15"
        NET_30 = "net_30", "Net 30"
        NET_45 = "net_45", "Net 45"
        NET_60 = "net_60", "Net 60"
        DUE_END_OF_MONTH = "due_end_of_month", "Due end of the month"
        DUE_END_OF_NEXT_MONTH = "due_end_of_next_month", "Due end of next month"

    class AccountsReceivable(models.TextChoices):
        ACCOUNTS_RECEIVABLE = "accounts_receivable", "Accounts Receivable"
        DOMESTIC = "accounts_receivable_domestic", "Accounts Receivable - Domestic"
        FOREIGN = "accounts_receivable_foreign", "Accounts Receivable - Foreign"

    class PortalLanguage(models.TextChoices):
        ENGLISH = "en", "English"
        HINDI = "hi", "Hindi"
        TAMIL = "ta", "Tamil"
        TELUGU = "te", "Telugu"
        MARATHI = "mr", "Marathi"
        BENGALI = "bn", "Bengali"
        GUJARATI = "gu", "Gujarati"

    class Salutation(models.TextChoices):
        MR = "mr", "Mr."
        MRS = "mrs", "Mrs."
        MS = "ms", "Ms."
        MISS = "miss", "Miss."
        DR = "dr", "Dr."

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="customers",
        null=True,
        blank=True,
    )
    customer_type = models.CharField(
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.BUSINESS,
        blank=True,
    )
    salutation = models.CharField(max_length=10, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    display_name = models.CharField(max_length=200, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(max_length=255, blank=True)
    phone_country_code = models.CharField(max_length=8, blank=True, default="+91")
    phone = models.CharField(max_length=20, blank=True)
    mobile_country_code = models.CharField(max_length=8, blank=True, default="+91")
    mobile = models.CharField(max_length=20, blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    tax_treatment = models.CharField(max_length=40, blank=True)
    place_of_supply = models.CharField(max_length=100, blank=True)
    currency = models.CharField(max_length=3, blank=True, default="INR")
    accounts_receivable = models.CharField(
        max_length=40,
        blank=True,
        default=AccountsReceivable.ACCOUNTS_RECEIVABLE,
    )
    payment_term_id = models.UUIDField(null=True, blank=True)
    payment_terms = models.CharField(
        max_length=40,
        blank=True,
        default=PaymentTerms.DUE_ON_RECEIPT,
    )
    currency_id = models.UUIDField(null=True, blank=True)
    opening_balance = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    receivables = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )
    unused_credits = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
    )
    synced_with_crm = models.BooleanField(default=False)
    portal_enabled = models.BooleanField(default=False)
    portal_language = models.CharField(
        max_length=8,
        blank=True,
        default=PortalLanguage.ENGLISH,
    )
    website = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)
    is_overdue = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        blank=True,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_customers",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "customers"
        ordering = ["display_name", "company_name"]

    def __str__(self):
        return self.display_name or self.company_name or str(self.id)

    @property
    def name(self):
        return self.display_name or self.company_name or ""

    @property
    def initials(self):
        parts = [part for part in (self.name or "").split() if part]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:2].upper()
        return f"{parts[0][0]}{parts[1][0]}".upper()


class CustomerAddress(models.Model):
    class AddressType(models.TextChoices):
        BILLING = "billing", "Billing"
        SHIPPING = "shipping", "Shipping"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="addresses",
        null=True,
        blank=True,
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.CASCADE,
        related_name="customer_addresses",
        null=True,
        blank=True,
    )
    address_type = models.CharField(
        max_length=10,
        choices=AddressType.choices,
        blank=True,
    )

    class Meta:
        db_table = "customer_addresses"
        ordering = ["address_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "address_type"],
                name="unique_customer_address_type",
            ),
        ]

    def __str__(self):
        return f"{self.customer_id}:{self.address_type}"


class CustomerContactPerson(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="contact_persons",
        null=True,
        blank=True,
    )
    salutation = models.CharField(max_length=10, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(max_length=255, blank=True)
    work_phone_country_code = models.CharField(max_length=8, blank=True, default="+91")
    work_phone = models.CharField(max_length=20, blank=True)
    mobile_country_code = models.CharField(max_length=8, blank=True, default="+91")
    mobile = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "customer_contact_persons"
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or str(self.id)


class CustomerSocialLink(TimeStampedModel):
    class Platform(models.TextChoices):
        WEBSITE = "website", "Website"
        FACEBOOK = "facebook", "Facebook"
        TWITTER = "twitter", "Twitter"
        LINKEDIN = "linkedin", "LinkedIn"
        INSTAGRAM = "instagram", "Instagram"
        YOUTUBE = "youtube", "YouTube"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="social_links",
        null=True,
        blank=True,
    )
    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        default=Platform.WEBSITE,
        blank=True,
    )
    url = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "customer_social_links"
        ordering = ["platform", "created_at"]

    def __str__(self):
        return f"{self.platform}:{self.url}" or str(self.id)


class CustomerPayment(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="customer_payments",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True,
    )
    payment_number = models.CharField(max_length=30)
    payment_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    payment_mode_id = models.UUIDField(null=True, blank=True)
    bank_account_id = models.UUIDField(null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "customer_payments"
        ordering = ["-payment_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "payment_number"],
                name="unique_org_payment_number",
            ),
        ]

    def __str__(self):
        return self.payment_number
