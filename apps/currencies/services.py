from django.shortcuts import get_object_or_404

from apps.currencies import constants
from apps.currencies.models import Currency
from apps.organizations.models import Organization
from apps.organizations.services import get_current_organization


def resolve_organization(user, organization_id=None):
    if organization_id:
        return get_object_or_404(Organization.objects.filter(owner=user), pk=organization_id)
    return get_current_organization(user)


def catalog_entry(code):
    code = (code or "").strip().upper()
    entry = constants.CURRENCY_CATALOG.get(code)
    if not entry:
        return None
    name, symbol, decimals = entry
    return {"code": code, "name": name, "symbol": symbol, "decimal_places": decimals}


def ensure_default_currencies(organization):
    """Create the base currency and the standard set the first time an organization opens Currencies."""
    if Currency.objects.filter(organization=organization).exists():
        base_code = (organization.currency or "").upper()
        if base_code and not Currency.objects.filter(organization=organization, code=base_code).exists():
            create_from_catalog(organization, base_code)
        return

    base_code = (organization.currency or "INR").upper()
    codes = [base_code] + [code for code in constants.DEFAULT_CURRENCIES if code != base_code]
    for code in codes:
        create_from_catalog(organization, code)


def create_from_catalog(organization, code):
    entry = catalog_entry(code) or {
        "code": code,
        "name": code,
        "symbol": code,
        "decimal_places": 2,
    }
    return Currency.objects.create(
        organization=organization,
        code=entry["code"],
        name=entry["name"],
        symbol=entry["symbol"],
        decimal_places=entry["decimal_places"],
    )


def currency_in_use(currency):
    from apps.customers.models import Customer

    return Customer.objects.filter(organization=currency.organization, currency=currency.code).exists()
