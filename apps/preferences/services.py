import re

from django.shortcuts import get_object_or_404

from apps.accounts.countries import COUNTRY_NAMES
from apps.organizations.models import Organization
from apps.organizations.services import get_current_organization
from apps.preferences.models import Preference


def resolve_organization(user, organization_id=None):
    if organization_id:
        return get_object_or_404(Organization.objects.filter(owner=user), pk=organization_id)
    return get_current_organization(user)


def get_or_create_preference(organization):
    preference, _created = Preference.objects.get_or_create(organization=organization)
    return preference


def country_name(code):
    return COUNTRY_NAMES.get((code or "").upper(), code or "")


def trn_label(country_code):
    return "TRN" if (country_code or "").upper() in {"AE", "SA"} else "GSTIN"


def live_next_number(model, field, organization, prefix, stored_next):
    """Highest existing number using this prefix + 1, never lower than the stored next number."""
    pattern = re.compile(rf"^{re.escape(prefix or '')}(\d+)$", re.IGNORECASE)
    highest = 0
    numbers = model.objects.filter(organization=organization).values_list(field, flat=True)
    for number in numbers:
        match = pattern.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return max(stored_next or 1, highest + 1)


def format_number(prefix, number):
    return f"{prefix or ''}{int(number):06d}"


def organization_placeholder_values(organization):
    owner = organization.owner
    street = " ".join(
        part for part in [organization.address_line1, organization.address_line2] if part
    )
    return {
        "ORGANIZATION.NAME": organization.name or "",
        "ORGANIZATION.STREET_ADDRESS": street,
        "ORGANIZATION.CITY": organization.city or "",
        "ORGANIZATION.STATE": organization.state or "",
        "ORGANIZATION.POSTAL_CODE": organization.postal_code or "",
        "ORGANIZATION.COUNTRY": country_name(organization.country),
        "ORGANIZATION.PHONE": organization.phone or "",
        "ORGANIZATION.EMAIL": getattr(owner, "email", "") or "",
        "ORGANIZATION.WEBSITE": organization.website or "",
        "ORGANIZATION.TRN_LABEL": trn_label(organization.country) if organization.gstin else "",
        "ORGANIZATION.TRN_VALUE": organization.gstin or "",
    }


SAMPLE_CONTACT = {
    "CONTACT.CONTACT_DISPLAYNAME": "Acme Trading LLC",
    "CONTACT.CONTACT_ATTENTION": "Accounts Department",
    "CONTACT.CONTACT_ADDRESS": "Office 1204, Business Bay Tower",
    "CONTACT.CONTACT_CITY": "Dubai",
    "CONTACT.CONTACT_STATE": "Dubai",
    "CONTACT.CONTACT_CODE": "00000",
    "CONTACT.CONTACT_COUNTRY": "United Arab Emirates",
    "CONTACT.CONTACT_PHONE": "+971 4 123 4567",
    "CONTACT.CONTACT_FAX": "",
    "CONTACT.TRN_LABEL": "TRN",
    "CONTACT.TRN": "100000000000003",
}


def contact_placeholder_values(customer=None, vendor=None, address_type="billing", organization=None):
    if customer is None and vendor is None:
        return dict(SAMPLE_CONTACT)

    contact = customer or vendor
    address = None
    if customer is not None:
        link = (
            customer.addresses.filter(address_type=address_type).select_related("address").first()
            or customer.addresses.select_related("address").first()
        )
        address = link.address if link else None

    lines = []
    if address:
        lines = [part for part in [address.address_line1, address.address_line2] if part]
    phone = ""
    if address and address.phone:
        phone = f"{address.phone_country_code or ''} {address.phone}".strip()
    elif getattr(contact, "phone", ""):
        phone = f"{getattr(contact, 'phone_country_code', '') or ''} {contact.phone}".strip()

    country_code = address.country if address and address.country else (
        organization.country if organization else ""
    )
    gstin = getattr(contact, "gstin", "") or ""
    return {
        "CONTACT.CONTACT_DISPLAYNAME": contact.display_name or contact.company_name or "",
        "CONTACT.CONTACT_ATTENTION": address.attention if address else "",
        "CONTACT.CONTACT_ADDRESS": " ".join(lines),
        "CONTACT.CONTACT_CITY": address.city if address else "",
        "CONTACT.CONTACT_STATE": address.state if address else "",
        "CONTACT.CONTACT_CODE": address.postal_code if address else "",
        "CONTACT.CONTACT_COUNTRY": country_name(country_code),
        "CONTACT.CONTACT_PHONE": phone,
        "CONTACT.CONTACT_FAX": address.fax if address else "",
        "CONTACT.TRN_LABEL": trn_label(country_code) if gstin else "",
        "CONTACT.TRN": gstin,
    }


PLACEHOLDER_RE = re.compile(r"\$\{([A-Z_.]+)\}")


def render_address(template, values):
    def replace(match):
        return values.get(match.group(1), "")

    rendered_lines = []
    for line in (template or "").splitlines():
        rendered = PLACEHOLDER_RE.sub(replace, line)
        rendered = re.sub(r"[ \t]+", " ", rendered).strip()
        if rendered:
            rendered_lines.append(rendered)
    return "\n".join(rendered_lines)


def unknown_placeholders(template, allowed):
    found = set(PLACEHOLDER_RE.findall(template or ""))
    return sorted(found - set(allowed))
