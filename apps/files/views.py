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
from apps.files.filters import FILE_TYPE_FILTERS, StoredFileFilter
from apps.files.models import StoredFile
from apps.files.serializers import StoredFileSerializer, StoredFileWriteSerializer
from apps.files.storage import delete_stored_file, save_uploaded_file
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

FILE_ID_KEYS = ("file_id", "document_id", "id")


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_file_queryset(user):
    return StoredFile.objects.filter(organization__owner=user).select_related(
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


def get_file_id_param(request):
    if any(key in request.query_params or key in request.data for key in FILE_ID_KEYS):
        file_id = (
            request.query_params.get("file_id")
            or request.query_params.get("document_id")
            or request.query_params.get("id")
            or request.data.get("file_id")
            or request.data.get("document_id")
            or request.data.get("id")
        )
        return parse_uuid(file_id, "file_id")
    return None, api_error(
        "file_id query parameter is required.",
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


def filtered_file_queryset(request):
    queryset = get_file_queryset(request.user)
    file_filter = StoredFileFilter(request.query_params, queryset=queryset)
    if not file_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=file_filter.errors)
    queryset, error_response = apply_sorting(file_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def file_counts(queryset):
    return {
        "all": queryset.count(),
        "pdf": queryset.filter(file_type=StoredFile.FileType.PDF).count(),
        "image": queryset.filter(file_type=StoredFile.FileType.IMAGE).count(),
        "spreadsheet": queryset.filter(file_type=StoredFile.FileType.SPREADSHEET).count(),
        "document": queryset.filter(file_type=StoredFile.FileType.DOCUMENT).count(),
        "other": queryset.filter(file_type=StoredFile.FileType.OTHER).count(),
    }


def file_response(stored_file):
    if not stored_file.storage_key or not default_storage.exists(stored_file.storage_key):
        return api_error(
            "File is not available.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    handle = default_storage.open(stored_file.storage_key, "rb")
    return FileResponse(
        handle,
        as_attachment=True,
        filename=stored_file.name,
        content_type=stored_file.mime_type or "application/octet-stream",
    )


def ensure_share_token(stored_file):
    if not stored_file.share_token:
        stored_file.share_token = uuid4().hex
        stored_file.save(update_fields=["share_token", "updated_at"])
    return stored_file.share_token


class FileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        if any(key in request.query_params for key in FILE_ID_KEYS):
            file_id, error_response = get_file_id_param(request)
            if error_response:
                return error_response
            stored_file = get_file_queryset(request.user).filter(pk=file_id).first()
            if not stored_file:
                return api_error(
                    "File not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return api_success(
                data=StoredFileSerializer(stored_file, context={"request": request}).data
            )

        queryset, error_response = filtered_file_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(
            request,
            queryset,
            serializer=StoredFileSerializer,
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
        serializer = StoredFileWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        name = serializer.validated_data.get("name") or Path(uploaded_file.name).name
        folder = serializer.validated_data.get("folder") or "All documents"
        stored_file = StoredFile.objects.create(
            organization=organization,
            created_by=request.user,
            name=name,
            folder=folder,
            mime_type=getattr(uploaded_file, "content_type", "") or "",
            file_size=uploaded_file.size or 0,
            file_type=StoredFile.type_from_name(name),
        )
        stored_file.storage_key = save_uploaded_file(
            uploaded_file,
            organization.id,
            stored_file.id,
        )
        stored_file.save(update_fields=["storage_key", "updated_at"])
        stored_file = get_file_queryset(request.user).get(pk=stored_file.pk)
        return api_success(
            data=StoredFileSerializer(stored_file, context={"request": request}).data,
            message="File uploaded successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        file_id, error_response = get_file_id_param(request)
        if error_response:
            return error_response
        stored_file = get_file_queryset(request.user).filter(pk=file_id).first()
        if not stored_file:
            return api_error(
                "File not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        storage_key = stored_file.storage_key
        stored_file.delete()
        delete_stored_file(storage_key)
        return api_success(message="File deleted successfully.")


class FileFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_file_queryset(request.user)
        data = {
            "title": "Upload File",
            "subtitle": "Add a new file to your documents",
            "folder": "All documents",
            "fields": {
                "file": {"label": "File", "required": True},
                "name": {"label": "Name", "required": False},
                "folder": {
                    "label": "Folder",
                    "required": False,
                    "default": "All documents",
                },
            },
            "counts": file_counts(queryset),
            "create_path": "/api/files/",
            "refresh_path": "/api/files/refresh/",
        }
        if any(key in request.query_params for key in FILE_ID_KEYS):
            file_id, error_response = get_file_id_param(request)
            if error_response:
                return error_response
            stored_file = get_file_queryset(request.user).filter(pk=file_id).first()
            if not stored_file:
                return api_error(
                    "File not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            data["title"] = "File"
            data["file"] = StoredFileSerializer(
                stored_file, context={"request": request}
            ).data
        return api_success(data=data)


class FileOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_file_queryset(request.user)
        return api_success(
            data={
                "title": "All Files",
                "section": "All documents",
                "counts": file_counts(queryset),
                "types": [
                    {"key": key, "label": label} for key, label in FILE_TYPE_FILTERS
                ],
                "sort_fields": [
                    {"key": "uploaded_time", "label": "Uploaded Time"},
                    {"key": "name", "label": "Name"},
                    {"key": "size", "label": "Size"},
                ],
                "default_sort": {"sort_by": "uploaded_time", "sort_order": "desc"},
                "form_path": "/api/files/form/",
                "actions": [
                    {
                        "key": "upload",
                        "label": "Upload File",
                        "description": "Add a new file to your documents",
                        "path": "/api/files/",
                    },
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "description": "Reload the latest files",
                        "path": "/api/files/refresh/",
                    },
                    {
                        "key": "download",
                        "label": "Download",
                        "path": "/api/files/download/",
                    },
                    {
                        "key": "share",
                        "label": "Share",
                        "path": "/api/files/share/",
                    },
                    {
                        "key": "delete",
                        "label": "Delete",
                        "path": "/api/files/",
                    },
                ],
            }
        )


class FileRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_file_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(
            request,
            queryset,
            serializer=StoredFileSerializer,
            serializer_context={"request": request},
        )
        if response is not None:
            response.data["message"] = "Files refreshed."
            return response
        return api_success(data=[], message="Files refreshed.")


class FileDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        file_id, error_response = get_file_id_param(request)
        if error_response:
            return error_response
        stored_file = get_file_queryset(request.user).filter(pk=file_id).first()
        if not stored_file:
            return api_error(
                "File not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return file_response(stored_file)


class FileShareView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_id, error_response = get_file_id_param(request)
        if error_response:
            return error_response
        stored_file = get_file_queryset(request.user).filter(pk=file_id).first()
        if not stored_file:
            return api_error(
                "File not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        token = ensure_share_token(stored_file)
        return api_success(
            data={
                "file_id": stored_file.id,
                "name": stored_file.name,
                "share_token": token,
                "share_url": request.build_absolute_uri(f"/api/files/shared/{token}/"),
                "download_url": request.build_absolute_uri(
                    f"/api/files/shared/{token}/download/"
                ),
            },
            message="Share link created.",
        )


class FileSharedView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        stored_file = StoredFile.objects.filter(share_token=token).first()
        if not stored_file:
            return api_error(
                "Share link is invalid or expired.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        data = StoredFileSerializer(stored_file, context={"request": request}).data
        data["download_url"] = request.build_absolute_uri(
            f"/api/files/shared/{token}/download/"
        )
        return api_success(data=data)


class FileSharedDownloadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request, token):
        stored_file = StoredFile.objects.filter(share_token=token).first()
        if not stored_file:
            return api_error(
                "Share link is invalid or expired.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return file_response(stored_file)
