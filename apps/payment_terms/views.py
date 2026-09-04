from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.payment_terms.filters import PaymentTermFilter
from apps.payment_terms.models import PaymentTerm
from apps.payment_terms.serializers import PaymentTermSerializer, PaymentTermWriteSerializer


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_payment_term_queryset(user):
    return PaymentTerm.objects.filter(organization__owner=user).select_related(
        "organization",
    )


def get_payment_term_id_param(request):
    payment_term_id = (
        request.query_params.get("payment_term_id")
        or request.query_params.get("id")
    )
    if not payment_term_id:
        return None, api_error(
            "payment_term_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return payment_term_id, None


class PaymentTermView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment_term_id = (
            request.query_params.get("payment_term_id")
            or request.query_params.get("id")
        )
        if payment_term_id:
            payment_term = get_object_or_404(
                get_payment_term_queryset(request.user),
                pk=payment_term_id,
            )
            return api_success(data=PaymentTermSerializer(payment_term).data)

        queryset = get_payment_term_queryset(request.user)
        payment_term_filter = PaymentTermFilter(request.query_params, queryset=queryset)
        if not payment_term_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=payment_term_filter.errors)

        response = paginate_queryset(
            request,
            payment_term_filter.qs.order_by("-created_at"),
            serializer=PaymentTermSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        organization = resolve_organization(
            request.user,
            request.data.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup before creating payment terms.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaymentTermWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        payment_term = serializer.save(organization=organization)
        return api_success(
            data=PaymentTermSerializer(payment_term).data,
            message="Payment term created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        payment_term_id, error_response = get_payment_term_id_param(request)
        if error_response:
            return error_response

        payment_term = get_object_or_404(
            get_payment_term_queryset(request.user),
            pk=payment_term_id,
        )
        serializer = PaymentTermWriteSerializer(payment_term, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        payment_term = serializer.save()
        return api_success(
            data=PaymentTermSerializer(payment_term).data,
            message="Payment term updated successfully.",
        )

    def patch(self, request):
        payment_term_id, error_response = get_payment_term_id_param(request)
        if error_response:
            return error_response

        payment_term = get_object_or_404(
            get_payment_term_queryset(request.user),
            pk=payment_term_id,
        )
        serializer = PaymentTermWriteSerializer(
            payment_term,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        payment_term = serializer.save()
        return api_success(
            data=PaymentTermSerializer(payment_term).data,
            message="Payment term updated successfully.",
        )

    def delete(self, request):
        payment_term_id, error_response = get_payment_term_id_param(request)
        if error_response:
            return error_response

        payment_term = get_object_or_404(
            get_payment_term_queryset(request.user),
            pk=payment_term_id,
        )
        payment_term.delete()
        return api_success(message="Payment term deleted successfully.")
