from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.vendors.filters import VendorFilter
from apps.vendors.models import Vendor, VendorPayment
from apps.vendors.payment_filters import VendorPaymentFilter
from apps.vendors.serializers import (
    VendorPaymentSerializer,
    VendorPaymentWriteSerializer,
    VendorSerializer,
    VendorWriteSerializer,
)


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_vendor_queryset(user):
    return Vendor.objects.filter(organization__owner=user).select_related(
        "organization",
        "payment_term",
        "created_by",
    )


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_vendor_id_param(request):
    vendor_id = request.query_params.get("vendor_id") or request.query_params.get("id")
    if not vendor_id:
        return None, api_error(
            "vendor_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return vendor_id, None


class VendorView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor_id = request.query_params.get("vendor_id") or request.query_params.get("id")
        if vendor_id:
            vendor = get_object_or_404(get_vendor_queryset(request.user), pk=vendor_id)
            return api_success(data=VendorSerializer(vendor).data)

        queryset = get_vendor_queryset(request.user)
        vendor_filter = VendorFilter(request.query_params, queryset=queryset)
        if not vendor_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=vendor_filter.errors)

        response = paginate_queryset(
            request,
            vendor_filter.qs.order_by("-created_at"),
            serializer=VendorSerializer,
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
                "Organization not found. Complete organization setup before creating vendors.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = VendorWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        created_by = serializer.validate_created_by_reference(request.user)
        vendor = serializer.save(organization=organization, created_by=created_by)
        return api_success(
            data=VendorSerializer(vendor).data,
            message="Vendor created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        vendor_id, error_response = get_vendor_id_param(request)
        if error_response:
            return error_response

        vendor = get_object_or_404(get_vendor_queryset(request.user), pk=vendor_id)
        serializer = VendorWriteSerializer(vendor, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        vendor = serializer.save()
        return api_success(
            data=VendorSerializer(vendor).data,
            message="Vendor updated successfully.",
        )

    def patch(self, request):
        vendor_id, error_response = get_vendor_id_param(request)
        if error_response:
            return error_response

        vendor = get_object_or_404(get_vendor_queryset(request.user), pk=vendor_id)
        serializer = VendorWriteSerializer(vendor, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        vendor = serializer.save()
        return api_success(
            data=VendorSerializer(vendor).data,
            message="Vendor updated successfully.",
        )

    def delete(self, request):
        vendor_id, error_response = get_vendor_id_param(request)
        if error_response:
            return error_response

        vendor = get_object_or_404(get_vendor_queryset(request.user), pk=vendor_id)
        vendor.delete()
        return api_success(message="Vendor deleted successfully.")


def get_vendor_payment_queryset(user):
    return VendorPayment.objects.filter(
        organization__owner=user,
    ).select_related("organization", "vendor")


def get_vendor_payment_id_param(request):
    vendor_payment_id = (
        request.query_params.get("vendor_payment_id")
        or request.query_params.get("id")
    )
    if not vendor_payment_id:
        return None, api_error(
            "vendor_payment_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return vendor_payment_id, None


class VendorPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor_payment_id = (
            request.query_params.get("vendor_payment_id")
            or request.query_params.get("id")
        )
        if vendor_payment_id:
            payment = get_object_or_404(
                get_vendor_payment_queryset(request.user),
                pk=vendor_payment_id,
            )
            return api_success(data=VendorPaymentSerializer(payment).data)

        queryset = get_vendor_payment_queryset(request.user)
        payment_filter = VendorPaymentFilter(request.query_params, queryset=queryset)
        if not payment_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=payment_filter.errors)

        response = paginate_queryset(
            request,
            payment_filter.qs.order_by("-created_at"),
            serializer=VendorPaymentSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        vendor_id = request.data.get("vendor_id")
        if not vendor_id:
            return api_error("vendor_id is required.", status_code=status.HTTP_400_BAD_REQUEST)

        get_object_or_404(get_vendor_queryset(request.user), pk=vendor_id)
        serializer = VendorPaymentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        payment = serializer.save()
        return api_success(
            data=VendorPaymentSerializer(payment).data,
            message="Vendor payment created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        vendor_payment_id, error_response = get_vendor_payment_id_param(request)
        if error_response:
            return error_response

        payment = get_object_or_404(
            get_vendor_payment_queryset(request.user),
            pk=vendor_payment_id,
        )
        serializer = VendorPaymentWriteSerializer(payment, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        payment = serializer.save()
        return api_success(
            data=VendorPaymentSerializer(payment).data,
            message="Vendor payment updated successfully.",
        )

    def patch(self, request):
        vendor_payment_id, error_response = get_vendor_payment_id_param(request)
        if error_response:
            return error_response

        payment = get_object_or_404(
            get_vendor_payment_queryset(request.user),
            pk=vendor_payment_id,
        )
        serializer = VendorPaymentWriteSerializer(
            payment,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        payment = serializer.save()
        return api_success(
            data=VendorPaymentSerializer(payment).data,
            message="Vendor payment updated successfully.",
        )

    def delete(self, request):
        vendor_payment_id, error_response = get_vendor_payment_id_param(request)
        if error_response:
            return error_response

        payment = get_object_or_404(
            get_vendor_payment_queryset(request.user),
            pk=vendor_payment_id,
        )
        payment.delete()
        return api_success(message="Vendor payment deleted successfully.")
