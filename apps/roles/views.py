from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.roles.filters import RoleFilter
from apps.roles.models import Role
from apps.roles.serializers import RoleSerializer, RoleWriteSerializer

DUPLICATE_CODE_MESSAGE = "A role with this role_code already exists."


def get_role_id_param(request):
    role_id = request.query_params.get("id")
    if not role_id:
        return None, api_error(
            "id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return role_id, None


def get_role_queryset(user):
    return Role.objects.filter(organization__owner=user)


def resolve_organization(user, organization_id=None):
    organizations = Organization.objects.filter(owner=user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def role_code_taken(organization_id, role_code, exclude_id=None):
    queryset = Role.objects.filter(organization_id=organization_id, role_code=role_code)
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)
    return queryset.exists()


class RoleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role_id = request.query_params.get("id")
        if role_id:
            role = get_object_or_404(get_role_queryset(request.user), pk=role_id)
            return api_success(data=RoleSerializer(role).data)

        queryset = get_role_queryset(request.user)
        role_filter = RoleFilter(request.query_params, queryset=queryset)
        if not role_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=role_filter.errors)

        response = paginate_queryset(
            request,
            role_filter.qs,
            serializer=RoleSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        organization = resolve_organization(request.user, request.data.get("organization_id"))
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup before creating roles.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RoleWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        if role_code_taken(organization.id, serializer.validated_data["role_code"]):
            return api_error(DUPLICATE_CODE_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)

        try:
            role = serializer.save(organization=organization)
        except IntegrityError:
            return api_error(DUPLICATE_CODE_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)
        return api_success(
            data=RoleSerializer(role).data,
            message="Role created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        role_id, error_response = get_role_id_param(request)
        if error_response:
            return error_response

        role = get_object_or_404(get_role_queryset(request.user), pk=role_id)
        serializer = RoleWriteSerializer(role, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        role_code = serializer.validated_data.get("role_code")
        if role_code and role_code_taken(role.organization_id, role_code, exclude_id=role.pk):
            return api_error(DUPLICATE_CODE_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)

        try:
            role = serializer.save()
        except IntegrityError:
            return api_error(DUPLICATE_CODE_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)
        return api_success(
            data=RoleSerializer(role).data,
            message="Role updated successfully.",
        )

    def delete(self, request):
        role_id, error_response = get_role_id_param(request)
        if error_response:
            return error_response

        role = get_object_or_404(get_role_queryset(request.user), pk=role_id)
        if role.is_system_role:
            return api_error(
                "System roles cannot be deleted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        role.delete()
        return api_success(message="Role deleted successfully.")
