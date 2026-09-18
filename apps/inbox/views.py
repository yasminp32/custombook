from pathlib import Path
from uuid import UUID, uuid4

from django.core.files.storage import default_storage
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.inbox.filters import InboxDocumentFilter
from apps.inbox.models import InboxDocument
from apps.inbox.serializers import InboxDocumentSerializer, InboxDocumentWriteSerializer
from apps.inbox.storage import delete_stored_file, save_uploaded_file
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset

SORT_FIELDS = {
    "uploaded_time": "created_at",
    "created_time": "created_at",
    "created_at": "created_at",
    "name": "name",
    "size": "file_size",
    "file_size": "file_size",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_document_queryset(user):
    return InboxDocument.objects.filter(organization__owner=user).select_related(
        "organization",
        "created_by",
    )


def parse_uuid(value, field_name="id"):
    if value is None or str(value).strip() == "":
        return None, api_error(
            f"{field_name} is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    raw = str(value).strip()
    if "{{" in raw or "}}" in raw:
        return None, api_error(
            f"{field_name} is still a Postman placeholder. Use the real UUID.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        return UUID(raw), None
    except (ValueError, AttributeError, TypeError):
        return None, api_error(
            f"{field_name} must be a valid UUID.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def get_document_id_param(request):
    if any(
        key in request.query_params or key in request.data
        for key in ("document_id", "inbox_id", "id")
    ):
        document_id = (
            request.query_params.get("document_id")
            or request.query_params.get("inbox_id")
            or request.query_params.get("id")
            or request.data.get("document_id")
            or request.data.get("inbox_id")
            or request.data.get("id")
        )
        return parse_uuid(document_id, "document_id")
    return None, api_error(
        "document_id query parameter is required.",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


def apply_sorting(queryset, query_params):
    sort_by = (query_params.get("sort_by") or "uploaded_time").strip().lower()
    sort_order = (query_params.get("sort_order") or "desc").strip().lower()
    field = SORT_FIELDS.get(sort_by)
    if not field:
        return None, api_error(
            "Invalid sort_by.",
            errors={"sort_by": f"Allowed values: {', '.join(SORT_FIELDS.keys())}."},
        )
    if sort_order not in ("asc", "desc"):
        return None, api_error(
            "Invalid sort_order.",
            errors={"sort_order": "Allowed values: asc, desc."},
        )
    prefix = "-" if sort_order == "desc" else ""
    return queryset.order_by(f"{prefix}{field}", "-created_at"), None


def filtered_document_queryset(request):
    queryset = get_document_queryset(request.user)
    document_filter = InboxDocumentFilter(request.query_params, queryset=queryset)
    if not document_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=document_filter.errors)
    queryset, error_response = apply_sorting(document_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def document_counts(queryset):
    return {
        "all": queryset.count(),
        "pdf": queryset.filter(file_type=InboxDocument.FileType.PDF).count(),
        "image": queryset.filter(file_type=InboxDocument.FileType.IMAGE).count(),
        "spreadsheet": queryset.filter(file_type=InboxDocument.FileType.SPREADSHEET).count(),
        "document": queryset.filter(file_type=InboxDocument.FileType.DOCUMENT).count(),
    }


def file_response(document):
    if not document.storage_key or not default_storage.exists(document.storage_key):
        return api_error(
            "File is not available.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    handle = default_storage.open(document.storage_key, "rb")
    response = FileResponse(
        handle,
        as_attachment=True,
        filename=document.name,
        content_type=document.mime_type or "application/octet-stream",
    )
    return response


def ensure_share_token(document):
    if not document.share_token:
        document.share_token = uuid4().hex
        document.save(update_fields=["share_token", "updated_at"])
    return document.share_token


class InboxView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        if any(
            key in request.query_params
            for key in ("document_id", "inbox_id", "id")
        ):
            document_id, error_response = get_document_id_param(request)
            if error_response:
                return error_response
            document = get_document_queryset(request.user).filter(pk=document_id).first()
            if not document:
                return api_error(
                    "Document not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return api_success(
                data=InboxDocumentSerializer(document, context={"request": request}).data
            )

        queryset, error_response = filtered_document_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(
            request,
            queryset,
            serializer=InboxDocumentSerializer,
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
                "Organization not found. Complete organization setup first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return api_error(
                "file is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = InboxDocumentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        name = serializer.validated_data.get("name") or Path(uploaded_file.name).name
        folder = serializer.validated_data.get("folder") or "Inbox"
        document = InboxDocument.objects.create(
            organization=organization,
            created_by=request.user,
            name=name,
            folder=folder,
            mime_type=getattr(uploaded_file, "content_type", "") or "",
            file_size=uploaded_file.size or 0,
            file_type=InboxDocument.type_from_name(name),
        )
        document.storage_key = save_uploaded_file(
            uploaded_file,
            organization.id,
            document.id,
        )
        document.save(update_fields=["storage_key", "updated_at"])
        document = get_document_queryset(request.user).get(pk=document.pk)
        return api_success(
            data=InboxDocumentSerializer(document, context={"request": request}).data,
            message="Document uploaded successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        document_id, error_response = get_document_id_param(request)
        if error_response:
            return error_response
        document = get_document_queryset(request.user).filter(pk=document_id).first()
        if not document:
            return api_error(
                "Document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        storage_key = document.storage_key
        document.delete()
        delete_stored_file(storage_key)
        return api_success(message="Document deleted successfully.")


class InboxFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_document_queryset(request.user)
        data = {
            "title": "Upload Document",
            "subtitle": "Add a new document to your inbox",
            "folder": "Inbox",
            "fields": {
                "file": {"label": "File", "required": True},
                "name": {"label": "Name", "required": False},
                "folder": {"label": "Folder", "required": False, "default": "Inbox"},
            },
            "counts": document_counts(queryset),
            "create_path": "/api/inbox/",
            "refresh_path": "/api/inbox/refresh/",
        }
        if any(key in request.query_params for key in ("document_id", "inbox_id", "id")):
            document_id, error_response = get_document_id_param(request)
            if error_response:
                return error_response
            document = get_document_queryset(request.user).filter(pk=document_id).first()
            if not document:
                return api_error(
                    "Document not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            data["title"] = "Document"
            data["document"] = InboxDocumentSerializer(
                document, context={"request": request}
            ).data
        return api_success(data=data)


class InboxOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_document_queryset(request.user)
        return api_success(
            data={
                "title": "Inbox",
                "section": "Recently received",
                "counts": document_counts(queryset),
                "sort_fields": [
                    {"key": "uploaded_time", "label": "Uploaded Time"},
                    {"key": "name", "label": "Name"},
                    {"key": "size", "label": "Size"},
                ],
                "default_sort": {"sort_by": "uploaded_time", "sort_order": "desc"},
                "file_types": [
                    {"key": key, "label": label}
                    for key, label in InboxDocument.FileType.choices
                ],
                "form_path": "/api/inbox/form/",
                "actions": [
                    {
                        "key": "upload",
                        "label": "Upload Document",
                        "description": "Add a new document to your inbox",
                        "path": "/api/inbox/",
                    },
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "description": "Reload the latest documents",
                        "path": "/api/inbox/refresh/",
                    },
                    {
                        "key": "download",
                        "label": "Download",
                        "path": "/api/inbox/download/",
                    },
                    {
                        "key": "share",
                        "label": "Share",
                        "path": "/api/inbox/share/",
                    },
                    {
                        "key": "delete",
                        "label": "Delete",
                        "path": "/api/inbox/",
                    },
                ],
            }
        )


class InboxRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_document_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(
            request,
            queryset,
            serializer=InboxDocumentSerializer,
            serializer_context={"request": request},
        )
        if response is not None:
            response.data["message"] = "Inbox documents refreshed."
            return response
        return api_success(data=[], message="Inbox documents refreshed.")


class InboxDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        document_id, error_response = get_document_id_param(request)
        if error_response:
            return error_response
        document = get_document_queryset(request.user).filter(pk=document_id).first()
        if not document:
            return api_error(
                "Document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return file_response(document)


class InboxShareView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        document_id, error_response = get_document_id_param(request)
        if error_response:
            return error_response
        document = get_document_queryset(request.user).filter(pk=document_id).first()
        if not document:
            return api_error(
                "Document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        token = ensure_share_token(document)
        share_path = f"/api/inbox/shared/{token}/"
        share_url = request.build_absolute_uri(share_path)
        return api_success(
            data={
                "document_id": document.id,
                "name": document.name,
                "share_token": token,
                "share_url": share_url,
                "download_url": request.build_absolute_uri(
                    f"/api/inbox/shared/{token}/download/"
                ),
            },
            message="Share link created.",
        )


class InboxSharedView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        document = InboxDocument.objects.filter(share_token=token).first()
        if not document:
            return api_error(
                "Share link is invalid or expired.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        data = InboxDocumentSerializer(document, context={"request": request}).data
        data["download_url"] = request.build_absolute_uri(
            f"/api/inbox/shared/{token}/download/"
        )
        return api_success(data=data)


class InboxSharedDownloadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request, token):
        document = InboxDocument.objects.filter(share_token=token).first()
        if not document:
            return api_error(
                "Share link is invalid or expired.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return file_response(document)
