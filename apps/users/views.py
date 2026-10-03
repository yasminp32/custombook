import logging

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
from apps.users.services import (
    DEFAULT_INVITE_ROLE,
    ensure_system_roles,
    resolve_user_organization,
    role_option,
    send_invite_email,
)

logger = logging.getLogger(__name__)

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
    return User.objects.filter(organization__owner=auth_user).select_related("role", "organization")


def resolve_organization(auth_user, organization_id=None):
    organization = resolve_user_organization(auth_user, organization_id)
    if organization_id and not organization:
        return get_object_or_404(Organization.objects.filter(owner=auth_user), pk=organization_id)
    return organization


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
        organization = resolve_organization(
            request.user,
            request.query_params.get("organization_id"),
        )
        if organization:
            queryset = queryset.filter(organization=organization)
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

        serializer = UserWriteSerializer(
            data=request.data,
            context={"organization": organization},
        )
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
        serializer = UserWriteSerializer(
            user,
            data=request.data,
            partial=partial,
            context={"organization": user.organization},
        )
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


class UserRoleOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = resolve_organization(
            request.user,
            request.query_params.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        roles = ensure_system_roles(organization)
        return api_success(
            data={
                "roles": [role_option(role) for role in roles],
                "default_role": DEFAULT_INVITE_ROLE,
            }
        )


class UserInviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization = resolve_organization(
            request.user,
            request.data.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup before inviting users.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        payload = request.data.copy()
        if not payload.get("role") and not payload.get("role_id"):
            payload["role"] = DEFAULT_INVITE_ROLE
        serializer = UserWriteSerializer(data=payload, context={"organization": organization})
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        if not serializer.validated_data.get("full_name"):
            return api_error(
                "Validation error",
                errors={"name": "Name is required."},
            )
        if email_taken(organization.id, serializer.validated_data["email"]):
            return api_error(DUPLICATE_EMAIL_MESSAGE, status_code=400)

        try:
            user = serializer.save(organization=organization, status=User.Status.ACTIVE)
        except IntegrityError:
            return api_error(DUPLICATE_EMAIL_MESSAGE, status_code=400)

        email_sent = True
        try:
            send_invite_email(user, organization, request.user)
        except Exception:
            logger.exception("Failed to send user invite to %s", user.email)
            email_sent = False

        user = get_team_user_queryset(request.user).get(pk=user.pk)
        message = "Invitation sent." if email_sent else "User invited. The invitation email could not be sent."
        data = UserSerializer(user).data
        data["email_sent"] = email_sent
        return api_success(data=data, message=message, status_code=status.HTTP_201_CREATED)
