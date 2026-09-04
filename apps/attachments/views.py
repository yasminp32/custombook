from pathlib import Path

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.attachments.filters import AttachmentFilter
from apps.attachments.models import Attachment
from apps.attachments.serializers import AttachmentSerializer, AttachmentWriteSerializer
from apps.attachments.storage import delete_stored_file, save_uploaded_file
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_attachment_queryset(user):
    return Attachment.objects.filter(organization__owner=user).select_related(
        "organization",
    )


def get_attachment_id_param(request):
    attachment_id = (
        request.query_params.get("attachment_id")
        or request.query_params.get("id")
    )
    if not attachment_id:
        return None, api_error(
            "attachment_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return attachment_id, None


class AttachmentView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        attachment_id = (
            request.query_params.get("attachment_id")
            or request.query_params.get("id")
        )
        if attachment_id:
            attachment = get_object_or_404(
                get_attachment_queryset(request.user),
                pk=attachment_id,
            )
            serializer = AttachmentSerializer(attachment, context={"request": request})
            return api_success(data=serializer.data)

        queryset = get_attachment_queryset(request.user)
        attachment_filter = AttachmentFilter(request.query_params, queryset=queryset)
        if not attachment_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=attachment_filter.errors)

        response = paginate_queryset(
            request,
            attachment_filter.qs.order_by("-created_at"),
            serializer=AttachmentSerializer,
            serializer_context={"request": request},
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
                "Organization not found. Complete organization setup before creating attachments.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request.FILES.get("file")
        serializer = AttachmentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        attachment = serializer.save(organization=organization)

        if uploaded_file:
            storage_key = save_uploaded_file(
                uploaded_file,
                organization.id,
                attachment.id,
            )
            attachment.file_name = Path(uploaded_file.name).name
            attachment.mime_type = getattr(uploaded_file, "content_type", "") or ""
            attachment.file_size = uploaded_file.size
            attachment.storage_key = storage_key
            attachment.save(
                update_fields=[
                    "file_name",
                    "mime_type",
                    "file_size",
                    "storage_key",
                    "updated_at",
                ]
            )

        response_serializer = AttachmentSerializer(attachment, context={"request": request})
        return api_success(
            data=response_serializer.data,
            message="Attachment created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        attachment_id, error_response = get_attachment_id_param(request)
        if error_response:
            return error_response

        attachment = get_object_or_404(
            get_attachment_queryset(request.user),
            pk=attachment_id,
        )
        serializer = AttachmentWriteSerializer(attachment, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        attachment = serializer.save()
        response_serializer = AttachmentSerializer(attachment, context={"request": request})
        return api_success(
            data=response_serializer.data,
            message="Attachment updated successfully.",
        )

    def patch(self, request):
        attachment_id, error_response = get_attachment_id_param(request)
        if error_response:
            return error_response

        attachment = get_object_or_404(
            get_attachment_queryset(request.user),
            pk=attachment_id,
        )
        serializer = AttachmentWriteSerializer(
            attachment,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        attachment = serializer.save()
        response_serializer = AttachmentSerializer(attachment, context={"request": request})
        return api_success(
            data=response_serializer.data,
            message="Attachment updated successfully.",
        )

    def delete(self, request):
        attachment_id, error_response = get_attachment_id_param(request)
        if error_response:
            return error_response

        attachment = get_object_or_404(
            get_attachment_queryset(request.user),
            pk=attachment_id,
        )
        storage_key = attachment.storage_key
        attachment.delete()
        delete_stored_file(storage_key)
        return api_success(message="Attachment deleted successfully.")
