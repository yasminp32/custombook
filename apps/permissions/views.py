from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.pagination import paginate_queryset
from apps.permissions.filters import RolePermissionFilter
from apps.permissions.models import RolePermission
from apps.permissions.serializers import (
    RolePermissionSerializer,
    RolePermissionWriteSerializer,
)

DUPLICATE_MESSAGE = "This role already has a permission for this module."


def get_permission_id_param(request):
    permission_id = request.query_params.get("permission_id") or request.query_params.get("id")
    if not permission_id:
        return None, api_error(
            "permission_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return permission_id, None


def get_permission_queryset(user):
    return RolePermission.objects.filter(role__organization__owner=user).select_related("role")


class PermissionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        permission_id = request.query_params.get("permission_id") or request.query_params.get("id")
        if permission_id:
            permission = get_object_or_404(get_permission_queryset(request.user), pk=permission_id)
            return api_success(data=RolePermissionSerializer(permission).data)

        queryset = get_permission_queryset(request.user)
        permission_filter = RolePermissionFilter(request.query_params, queryset=queryset)
        if not permission_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=permission_filter.errors)

        response = paginate_queryset(
            request,
            permission_filter.qs,
            serializer=RolePermissionSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        serializer = RolePermissionWriteSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            permission = serializer.save()
        except IntegrityError:
            return api_error(DUPLICATE_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)

        return api_success(
            data=RolePermissionSerializer(permission).data,
            message="Permission created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        permission_id, error_response = get_permission_id_param(request)
        if error_response:
            return error_response

        permission = get_object_or_404(get_permission_queryset(request.user), pk=permission_id)
        serializer = RolePermissionWriteSerializer(
            permission,
            data=request.data,
            partial=partial,
            context={"request": request},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            permission = serializer.save()
        except IntegrityError:
            return api_error(DUPLICATE_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)

        return api_success(
            data=RolePermissionSerializer(permission).data,
            message="Permission updated successfully.",
        )

    def delete(self, request):
        permission_id, error_response = get_permission_id_param(request)
        if error_response:
            return error_response

        permission = get_object_or_404(get_permission_queryset(request.user), pk=permission_id)
        permission.delete()
        return api_success(message="Permission deleted successfully.")
