from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.users.filters import UserFilter
from apps.users.models import User
from apps.users.serializers import UserSerializer, UserWriteSerializer

DUPLICATE_EMAIL_MESSAGE = "A user with this email already exists."


def get_user_id_param(request):
    user_id = request.query_params.get("id")
    if not user_id:
        return None, api_error(
            "id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return user_id, None


def get_team_user_queryset(auth_user):
    return User.objects.filter(organization__owner=auth_user)


def resolve_organization(auth_user, organization_id=None):
    organizations = Organization.objects.filter(owner=auth_user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def email_taken(organization_id, email, exclude_id=None):
    queryset = User.objects.filter(organization_id=organization_id, email__iexact=email)
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)
    return queryset.exists()


class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get("id")
        if user_id:
            user = get_object_or_404(get_team_user_queryset(request.user), pk=user_id)
            return api_success(data=UserSerializer(user).data)

        queryset = get_team_user_queryset(request.user)
        user_filter = UserFilter(request.query_params, queryset=queryset)
        if not user_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=user_filter.errors)

        response = paginate_queryset(
            request,
            user_filter.qs,
            serializer=UserSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        organization = resolve_organization(request.user, request.data.get("organization_id"))
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup before creating users.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = UserWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        if email_taken(organization.id, serializer.validated_data["email"]):
            return api_error(DUPLICATE_EMAIL_MESSAGE, status_code=400)

        try:
            user = serializer.save(organization=organization)
        except IntegrityError:
            return api_error(DUPLICATE_EMAIL_MESSAGE, status_code=400)
        return api_success(
            data=UserSerializer(user).data,
            message="User created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        user_id, error_response = get_user_id_param(request)
        if error_response:
            return error_response

        user = get_object_or_404(get_team_user_queryset(request.user), pk=user_id)
        serializer = UserWriteSerializer(user, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        email = serializer.validated_data.get("email")
        if email and email_taken(user.organization_id, email, exclude_id=user.pk):
            return api_error(DUPLICATE_EMAIL_MESSAGE, status_code=400)

        try:
            user = serializer.save()
        except IntegrityError:
            return api_error(DUPLICATE_EMAIL_MESSAGE, status_code=400)
        return api_success(
            data=UserSerializer(user).data,
            message="User updated successfully.",
        )

    def delete(self, request):
        user_id, error_response = get_user_id_param(request)
        if error_response:
            return error_response

        user = get_object_or_404(get_team_user_queryset(request.user), pk=user_id)
        user.delete()
        return api_success(message="User deleted successfully.")
