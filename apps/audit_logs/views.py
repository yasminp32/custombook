from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.audit_logs.filters import AuditLogFilter
from apps.audit_logs.models import AuditLog
from apps.audit_logs.serializers import AuditLogSerializer, AuditLogWriteSerializer
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.users.models import User


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def resolve_audit_user(auth_user, user_id=None):
    if not auth_user:
        return None
    team_users = User.objects.filter(organization__owner=auth_user)
    if user_id:
        return team_users.filter(pk=user_id).first()
    return team_users.filter(email__iexact=auth_user.email).first()


def get_audit_log_queryset(user):
    return AuditLog.objects.filter(organization__owner=user).select_related(
        "organization",
        "user",
    )


def get_audit_log_id_param(request):
    audit_log_id = request.query_params.get("audit_log_id") or request.query_params.get("id")
    if not audit_log_id:
        return None, api_error(
            "audit_log_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return audit_log_id, None


class AuditLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        audit_log_id = request.query_params.get("audit_log_id") or request.query_params.get("id")
        if audit_log_id:
            audit_log = get_object_or_404(
                get_audit_log_queryset(request.user),
                pk=audit_log_id,
            )
            return api_success(data=AuditLogSerializer(audit_log).data)

        queryset = get_audit_log_queryset(request.user)
        audit_filter = AuditLogFilter(request.query_params, queryset=queryset)
        if not audit_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=audit_filter.errors)

        response = paginate_queryset(
            request,
            audit_filter.qs.order_by("-occurred_at", "-created_at"),
            serializer=AuditLogSerializer,
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
                "Organization not found. Complete organization setup before creating audit logs.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AuditLogWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        user_id = serializer.validated_data.get("user_id")
        audit_user = resolve_audit_user(request.user, user_id)
        if user_id and not audit_user:
            return api_error("Validation error", errors={"user_id": ["User not found."]})
        audit_log = serializer.save(organization=organization, user=audit_user)
        return api_success(
            data=AuditLogSerializer(audit_log).data,
            message="Audit log created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return api_error(
            "Audit logs are immutable and cannot be updated.",
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def patch(self, request):
        return api_error(
            "Audit logs are immutable and cannot be updated.",
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def delete(self, request):
        return api_error(
            "Audit logs are immutable and cannot be deleted.",
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
