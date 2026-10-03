from django.db import IntegrityError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.payment_gateways.constants import GATEWAY_MAP, METHOD_MAP
from apps.payment_gateways.models import OrganizationPaymentGateway
from apps.payment_gateways.services import gateway_payload, method_payload, resolve_organization, setup_map

NO_ORGANIZATION_MESSAGE = "Organization not found. Complete organization setup first."


def organization_id_from(request):
    return request.query_params.get("organization_id") or request.data.get("organization_id")


def load_organization(request):
    organization = resolve_organization(request.user, organization_id_from(request))
    if not organization:
        return None, api_error(NO_ORGANIZATION_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)
    return organization, None


def gateway_code_from(request):
    return (request.query_params.get("gateway_code") or request.data.get("gateway_code") or "").strip()


def payment_method_from(request):
    return (
        request.query_params.get("payment_method") or request.data.get("payment_method") or ""
    ).strip()


class PaymentGatewayIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        configured = setup_map(organization)
        methods = []
        for code, label in METHOD_MAP.items():
            payload = method_payload(code, configured)
            methods.append(
                {
                    "payment_method": code,
                    "label": label,
                    "gateway_count": payload["count"],
                    "url": request.build_absolute_uri(
                        f"/api/payment-gateways/list/?payment_method={code}"
                    ),
                }
            )
        return api_success(
            data={
                "organization_id": str(organization.id),
                "organization_name": organization.name,
                "payment_methods": methods,
            }
        )


class PaymentGatewayListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment_method = payment_method_from(request)
        if payment_method not in METHOD_MAP:
            return api_error(
                "Invalid payment_method. Allowed values: " + ", ".join(METHOD_MAP) + ".",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        organization, error = load_organization(request)
        if error:
            return error
        return api_success(data=method_payload(payment_method, setup_map(organization)))


class PaymentGatewayDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        gateway_code = gateway_code_from(request)
        if gateway_code not in GATEWAY_MAP:
            return api_error(
                "Invalid gateway_code. Allowed values: " + ", ".join(GATEWAY_MAP) + ".",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        organization, error = load_organization(request)
        if error:
            return error
        return api_success(data=gateway_payload(gateway_code, setup_map(organization)))


class PaymentGatewaySetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        gateway_code = gateway_code_from(request)
        if gateway_code not in GATEWAY_MAP:
            return api_error(
                "Invalid gateway_code. Allowed values: " + ", ".join(GATEWAY_MAP) + ".",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        organization, error = load_organization(request)
        if error:
            return error
        try:
            row, _created = OrganizationPaymentGateway.objects.get_or_create(
                organization=organization,
                gateway_code=gateway_code,
                defaults={"is_setup": True},
            )
        except IntegrityError:
            row = OrganizationPaymentGateway.objects.get(
                organization=organization,
                gateway_code=gateway_code,
            )
        if not row.is_setup:
            row.is_setup = True
            row.save(update_fields=["is_setup", "updated_at"])
        return api_success(
            data=gateway_payload(gateway_code, setup_map(organization)),
            message=f"{GATEWAY_MAP[gateway_code]['name']} set up successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        gateway_code = gateway_code_from(request)
        if gateway_code not in GATEWAY_MAP:
            return api_error(
                "Invalid gateway_code. Allowed values: " + ", ".join(GATEWAY_MAP) + ".",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        organization, error = load_organization(request)
        if error:
            return error
        OrganizationPaymentGateway.objects.filter(
            organization=organization,
            gateway_code=gateway_code,
        ).delete()
        return api_success(
            data=gateway_payload(gateway_code, setup_map(organization)),
            message=f"{GATEWAY_MAP[gateway_code]['name']} setup removed.",
        )
