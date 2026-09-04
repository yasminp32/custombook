from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.pagination import paginate_queryset
from apps.roles.filters import RoleFilter
from apps.roles.models import Role
from apps.roles.serializers import RoleSerializer, RoleWriteSerializer


def get_role_id_param(request):
    role_id = request.query_params.get("id")
    if not role_id:
        return None, api_error(
            "id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return role_id, None


class RoleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role_id = request.query_params.get("id")
        if role_id:
            role = get_object_or_404(Role, pk=role_id)
            return api_success(data=RoleSerializer(role).data)

        queryset = Role.objects.all()
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
        serializer = RoleWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        role = serializer.save()
        return api_success(
            data=RoleSerializer(role).data,
            message="Role created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        role_id, error_response = get_role_id_param(request)
        if error_response:
            return error_response

        role = get_object_or_404(Role, pk=role_id)
        serializer = RoleWriteSerializer(role, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        role = serializer.save()
        return api_success(
            data=RoleSerializer(role).data,
            message="Role updated successfully.",
        )

    def patch(self, request):
        role_id, error_response = get_role_id_param(request)
        if error_response:
            return error_response

        role = get_object_or_404(Role, pk=role_id)
        serializer = RoleWriteSerializer(role, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        role = serializer.save()
        return api_success(
            data=RoleSerializer(role).data,
            message="Role updated successfully.",
        )

    def delete(self, request):
        role_id, error_response = get_role_id_param(request)
        if error_response:
            return error_response

        role = get_object_or_404(Role, pk=role_id)
        if role.is_system_role:
            return api_error(
                "System roles cannot be deleted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        role.delete()
        return api_success(message="Role deleted successfully.")
