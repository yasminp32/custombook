from django.shortcuts import get_object_or_404

from apps.accounts.countries import COUNTRY_NAMES
from apps.organizations.models import Organization
from apps.organizations.services import get_current_organization
from apps.pdf_templates.constants import (
    DEFAULT_NOTES,
    DEFAULT_TERMS,
    DOCUMENT_TYPE_MAP,
    STANDARD_TEMPLATE_NAME,
    THEME_MAP,
)
from apps.pdf_templates.models import PdfTemplate
from apps.preferences.services import get_or_create_preference


def resolve_organization(user, organization_id=None):
    if organization_id:
        return get_object_or_404(Organization.objects.filter(owner=user), pk=organization_id)
    return get_current_organization(user)


def ensure_standard_templates(organization, document_type=None):
    codes = [document_type] if document_type else list(DOCUMENT_TYPE_MAP)
    for code in codes:
        template, created = PdfTemplate.objects.get_or_create(
            organization=organization,
            document_type=code,
            name=STANDARD_TEMPLATE_NAME,
            defaults={"theme": "blue", "is_default": True, "is_system": True},
        )
        if created:
            continue
        if not template.is_system:
            template.is_system = True
            template.save(update_fields=["is_system", "updated_at"])
        if not PdfTemplate.objects.filter(
            organization=organization,
            document_type=code,
            is_default=True,
        ).exists():
            template.is_default = True
            template.save(update_fields=["is_default", "updated_at"])


def set_default_template(template):
    PdfTemplate.objects.filter(
        organization=template.organization,
        document_type=template.document_type,
        is_default=True,
    ).exclude(pk=template.pk).update(is_default=False)
    if not template.is_default:
        template.is_default = True
        template.save(update_fields=["is_default", "updated_at"])


def next_custom_name(organization, document_type):
    base = "Custom Template"
    existing = set(
        PdfTemplate.objects.filter(organization=organization, document_type=document_type).values_list(
            "name",
            flat=True,
        )
    )
    if base not in existing:
        return base
    number = 2
    while f"{base} {number}" in existing:
        number += 1
    return f"{base} {number}"


def _country_name(code):
    return COUNTRY_NAMES.get((code or "").upper(), code or "")


def _notes_and_terms(organization, document_type):
    preference = get_or_create_preference(organization)
    if document_type == "quotes":
        notes = preference.quote_notes or DEFAULT_NOTES
        terms = preference.quote_terms or DEFAULT_TERMS
    else:
        notes = preference.invoice_notes or DEFAULT_NOTES
        terms = preference.invoice_terms or DEFAULT_TERMS
    return notes, terms


SAMPLE_LINES = (
    {
        "item": "Brochure Design",
        "description": "Electronic Design (Layout + Color)",
        "quantity": "1.00",
        "rate": "300.00",
        "tax": "21.60",
        "amount": "356.30",
    },
    {
        "item": "Web Design Package/Template - Basic",
        "description": "Estimate Theme...",
        "quantity": "1.00",
        "rate": "250.00",
        "tax": "11.75",
        "amount": "288.80",
    },
    {
        "item": "Print Ad - Basic - Color",
        "description": "Print Ad 1/4 page Color",
        "quantity": "1.00",
        "rate": "80.00",
        "tax": "19.00",
        "amount": "99.60",
    },
)


def build_preview(template):
    organization = template.organization
    document = DOCUMENT_TYPE_MAP[template.document_type]
    theme = THEME_MAP[template.theme]
    currency = (organization.currency or "AED").upper()
    city = organization.city or "Dubai"
    country = _country_name(organization.country) or "United Arab Emirates"
    trn = organization.gstin or "100123456700003"
    phone = organization.phone or "9967484826"
    email = getattr(organization.owner, "email", "") or "misellaneous4825@gmail.com"
    notes, terms = _notes_and_terms(organization, template.document_type)
    lines = []
    for index, line in enumerate(SAMPLE_LINES, start=1):
        lines.append({"number": index, **line})
    bank = None
    if template.bank_details_set:
        bank = {
            "bank_name": template.bank_name,
            "account_number": template.account_number,
            "ifsc_swift_code": template.ifsc_swift_code,
            "branch": template.branch,
        }
    return {
        "theme": template.theme,
        "theme_label": theme["label"],
        "theme_color": theme["color"],
        "document_title": document["title"],
        "document_number": document["number"],
        "header_amount": f"{currency}562.75",
        "company": {
            "name": organization.name or "Your Company",
            "city": city,
            "country": country,
            "trn_label": "TRN" if (organization.country or "").upper() in {"AE", "SA"} else "GSTIN",
            "trn": trn,
            "phone": phone,
            "email": email,
        },
        "bill_to": {
            "name": "Jack & Joe Trading",
            "address": "Box No. 576",
            "city": "Dubai",
            "postal_line": "94588 Dubai",
            "country": "Emirates",
        },
        "subject": "Description",
        "invoice_date": "11 Aug 2026",
        "invoice_date_label": "Invoice Date",
        "terms_label": "Terms",
        "terms": "Due on Receipt",
        "due_date": "11 Aug 2026",
        "due_date_label": "Due Date",
        "order_number": "SO-17",
        "order_number_label": "Order #",
        "columns": ["#", "Item & Description", "Qty", "Rate", "Tax", "Amount"],
        "lines": lines,
        "sub_total": {
            "quantity": "0.00",
            "rate": "630.00",
            "tax": "52.75",
            "amount": "756.60",
        },
        "total": {"currency": currency, "amount": "642.75"},
        "payment_retention": "18.00",
        "payment_made": "100.00",
        "balance_due": {"currency": currency, "amount": "62.75"},
        "tax_summary": {
            "currency": currency,
            "rows": [
                {
                    "name": "Sample Tax1 (4.10%)",
                    "taxable_amount": "516.00",
                    "tax_amount": "21.80",
                },
                {
                    "name": "Sample Tax2 (3.00%)",
                    "taxable_amount": "390.00",
                    "tax_amount": "11.75",
                },
            ],
            "taxable_total": "906.00",
            "tax_total": "32.75",
        },
        "notes": notes,
        "terms_and_conditions": terms,
        "bank_details": bank,
        "signature": {
            "signatory_name": template.signatory_name,
            "hint": "Signature will appear at the bottom of the PDF",
        },
    }
