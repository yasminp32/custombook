from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.branches.constants import MAX_BRANCHES_PER_ORGANIZATION
from apps.branches.filters import BranchFilter
from apps.branches.models import Branch
from apps.branches.serializers import BranchSerializer, BranchWriteSerializer
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_user_branch_queryset(user):
    return Branch.objects.filter(organization__owner=user).select_related(
        "organization",
        "address",
    )


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_branch_id_param(request):
    branch_id = request.query_params.get("id")
    if not branch_id:
        return None, api_error(
            "id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return branch_id, None


def get_branch_for_user(request, branch_id):
    return get_object_or_404(get_user_branch_queryset(request.user), pk=branch_id)


class BranchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        branch_id = request.query_params.get("id")
        if branch_id:
            branch = get_branch_for_user(request, branch_id)
            return api_success(data=BranchSerializer(branch).data)

        queryset = get_user_branch_queryset(request.user)
        branch_filter = BranchFilter(request.query_params, queryset=queryset)
        if not branch_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=branch_filter.errors)

        filtered_queryset = branch_filter.qs.order_by("-created_at")
        response = paginate_queryset(
            request,
            filtered_queryset,
            serializer=BranchSerializer,
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
                "Organization not found. Complete organization setup before creating branches.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if organization.branches.count() >= MAX_BRANCHES_PER_ORGANIZATION:
            return api_error(
                f"Maximum of {MAX_BRANCHES_PER_ORGANIZATION} branches allowed per organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BranchWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        branch = serializer.save(organization=organization)
        return api_success(
            data=BranchSerializer(branch).data,
            message="Branch created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        branch_id, error_response = get_branch_id_param(request)
        if error_response:
            return error_response

        branch = get_branch_for_user(request, branch_id)
        serializer = BranchWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        branch = serializer.update(branch, serializer.validated_data)
        return api_success(
            data=BranchSerializer(branch).data,
            message="Branch updated successfully.",
        )

    def patch(self, request):
        branch_id, error_response = get_branch_id_param(request)
        if error_response:
            return error_response

        branch = get_branch_for_user(request, branch_id)
        serializer = BranchWriteSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        branch = serializer.update(branch, serializer.validated_data)
        return api_success(
            data=BranchSerializer(branch).data,
            message="Branch updated successfully.",
        )

    def delete(self, request):
        branch_id, error_response = get_branch_id_param(request)
        if error_response:
            return error_response

        branch = get_branch_for_user(request, branch_id)
        branch.delete()
        return api_success(message="Branch deleted successfully.")
