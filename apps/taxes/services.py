import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.accounts.countries import COUNTRY_NAMES
from apps.organizations.gst import validate_gstin
from apps.organizations.models import Organization
from apps.organizations.services import get_current_organization
from apps.taxes.constants import INTERNATIONAL_TRADE_NOTE_AE
from apps.taxes.models import TaxRate, TaxSettings

TRN_PATTERN = re.compile(r"^\d{15}$")


def resolve_organization(user, organization_id=None):
    if organization_id:
        return get_object_or_404(Organization.objects.filter(owner=user), pk=organization_id)
    return get_current_organization(user)


def country_name(code):
    return COUNTRY_NAMES.get((code or "").upper(), code or "")


def tax_number_label(country_code):
    return "TRN" if (country_code or "").upper() in {"AE", "SA"} else "GSTIN"


def international_trade_label(country_code):
    name = country_name(country_code) or "your country"
    return f"Enable trade with contacts outside {name}"


def international_trade_note(country_code):
    if (country_code or "").upper() == "AE":
        return INTERNATIONAL_TRADE_NOTE_AE
    return (
        "Enable this option if you do business with contacts outside your country, "
        "including reverse charge handling."
    )


def default_rates_for(country_code):
    if (country_code or "").upper() == "IN":
        return (("GST", Decimal("18.00"), True), ("Zero Rate", Decimal("0.00"), False))
    return (("VAT", Decimal("5.00"), True), ("Zero Rate", Decimal("0.00"), False))


def get_or_create_settings(organization):
    settings_row, created = TaxSettings.objects.get_or_create(
        organization=organization,
        defaults={
            "is_vat_registered": organization.is_gst_registered,
            "tax_registration_number": organization.gstin or "",
        },
    )
    if created and organization.is_gst_registered and not settings_row.reporting_period:
        settings_row.reporting_period = TaxSettings.ReportingPeriod.CUSTOM
        settings_row.save(update_fields=["reporting_period"])
    return settings_row


def ensure_default_taxes(organization):
    get_or_create_settings(organization)
    if TaxRate.objects.filter(organization=organization).exists():
        return
    for name, rate, is_default in default_rates_for(organization.country):
        TaxRate.objects.create(
            organization=organization,
            name=name,
            rate=rate,
            tax_type=TaxRate.TaxType.TAX,
            is_default=is_default,
        )


def normalize_tax_number(country_code, number):
    value = (number or "").strip().upper()
    country = (country_code or "").upper()
    if country == "IN":
        try:
            return validate_gstin(value)
        except ValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else "Invalid GSTIN format."
            raise ValueError(message) from exc
    if country in {"AE", "SA"}:
        if not TRN_PATTERN.match(value):
            raise ValueError("TRN must be 15 digits.")
        return value
    if not re.match(r"^[A-Z0-9]{5,20}$", value):
        raise ValueError("Tax registration number must be 5 to 20 letters or digits.")
    return value


def set_default_tax(tax):
    TaxRate.objects.filter(organization=tax.organization, is_default=True).exclude(pk=tax.pk).update(
        is_default=False
    )
    if not tax.is_default:
        tax.is_default = True
        tax.save(update_fields=["is_default", "updated_at"])


def sync_organization_tax(organization, settings_row):
    organization.is_gst_registered = settings_row.is_vat_registered
    organization.gstin = settings_row.tax_registration_number if settings_row.is_vat_registered else organization.gstin
    if settings_row.is_vat_registered:
        organization.gstin = settings_row.tax_registration_number
    organization.save(update_fields=["is_gst_registered", "gstin", "updated_at"])


def group_rate(members):
    total = sum((member.rate for member in members), Decimal("0.00"))
    return total.quantize(Decimal("0.01"))


@transaction.atomic
def save_group_members(tax, members):
    tax.members.set(members)
    tax.rate = group_rate(members)
    tax.save(update_fields=["rate", "updated_at"])
    return tax
