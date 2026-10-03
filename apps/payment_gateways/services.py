from django.shortcuts import get_object_or_404

from apps.organizations.models import Organization
from apps.organizations.services import get_current_organization
from apps.payment_gateways.constants import GATEWAY_MAP, METHOD_GATEWAYS, METHOD_MAP
from apps.payment_gateways.models import OrganizationPaymentGateway


def resolve_organization(user, organization_id=None):
    if organization_id:
        return get_object_or_404(Organization.objects.filter(owner=user), pk=organization_id)
    return get_current_organization(user)


def setup_map(organization):
    return {
        row.gateway_code: row
        for row in OrganizationPaymentGateway.objects.filter(organization=organization, is_setup=True)
    }


def gateway_payload(code, configured):
    gateway = GATEWAY_MAP[code]
    is_setup = code in configured
    return {
        "gateway_code": code,
        "name": gateway["name"],
        "description": gateway["description"],
        "is_preferred": gateway["is_preferred"],
        "preferred_label": "Preferred" if gateway["is_preferred"] else "",
        "is_setup": is_setup,
        "action_label": "Edit" if is_setup else "Setup",
        "setup_id": str(configured[code].id) if is_setup else None,
    }


def method_payload(method_code, configured):
    gateways = [gateway_payload(code, configured) for code in METHOD_GATEWAYS[method_code]]
    return {
        "payment_method": method_code,
        "label": METHOD_MAP[method_code],
        "count": len(gateways),
        "gateways": gateways,
    }
