from collections import defaultdict
from uuid import UUID

from django.db import IntegrityError
from django.db.models import Count
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as SerializerValidationError
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.files.models import StoredFile
from apps.folders.filters import FolderFilter
from apps.folders.models import Folder
from apps.folders.serializers import FolderSerializer, FolderWriteSerializer
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset

SORT_FIELDS = {
    "name": "name",
    "created_time": "created_at",
    "created_at": "created_at",
    "file_count": "file_count",
}

FOLDER_ID_KEYS = ("folder_id", "id")


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_folder_queryset(user):
    return Folder.objects.filter(organization__owner=user).select_related(
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


def get_folder_id_param(request):
    if any(key in request.query_params or key in request.data for key in FOLDER_ID_KEYS):
        folder_id = (
            request.query_params.get("folder_id")
            or request.query_params.get("id")
            or request.data.get("folder_id")
            or request.data.get("id")
        )
        return parse_uuid(folder_id, "folder_id")
    return None, api_error(
        "folder_id query parameter is required.",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


def build_file_counts(user):
    counts = defaultdict(int)
    rows = (
        StoredFile.objects.filter(organization__owner=user)
        .annotate(folder_key=Lower("folder"))
        .values("organization_id", "folder_key")
        .annotate(total=Count("id"))
    )
    for row in rows:
        counts[(str(row["organization_id"]), row["folder_key"] or "")] = row["total"]
    return counts


def apply_sorting(queryset, query_params, file_counts):
    sort_by = (query_params.get("sort_by") or "name").strip().lower()
    sort_order = (query_params.get("sort_order") or "asc").strip().lower()
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
    if field == "file_count":
        folders = list(queryset)
        reverse = sort_order == "desc"

        def count_for(folder):
            key = (str(folder.organization_id), (folder.name or "").strip().lower())
            return file_counts.get(key, 0)

        folders.sort(key=lambda row: (count_for(row), row.name.lower()), reverse=reverse)
        return folders, None
    prefix = "-" if sort_order == "desc" else ""
    return queryset.order_by(f"{prefix}{field}", "name"), None


def filtered_folder_queryset(request):
    queryset = get_folder_queryset(request.user)
    folder_filter = FolderFilter(request.query_params, queryset=queryset)
    if not folder_filter.is_valid():
        return None, None, api_error("Invalid filter parameters.", errors=folder_filter.errors)
    file_counts = build_file_counts(request.user)
    queryset, error_response = apply_sorting(
        folder_filter.qs,
        request.query_params,
        file_counts,
    )
    if error_response:
        return None, None, error_response
    return queryset, file_counts, None


class FolderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if any(key in request.query_params for key in FOLDER_ID_KEYS):
            folder_id, error_response = get_folder_id_param(request)
            if error_response:
                return error_response
            folder = get_folder_queryset(request.user).filter(pk=folder_id).first()
            if not folder:
                return api_error(
                    "Folder not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            file_counts = build_file_counts(request.user)
            return api_success(
                data=FolderSerializer(
                    folder,
                    context={"request": request, "file_counts": file_counts},
                ).data
            )

        queryset, file_counts, error_response = filtered_folder_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(
            request,
            queryset,
            serializer=FolderSerializer,
            serializer_context={"request": request, "file_counts": file_counts},
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
        serializer = FolderWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            folder = serializer.save(
                organization=organization,
                created_by=request.user,
            )
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "A folder with this name already exists.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        folder = get_folder_queryset(request.user).get(pk=folder.pk)
        file_counts = build_file_counts(request.user)
        return api_success(
            data=FolderSerializer(
                folder,
                context={"request": request, "file_counts": file_counts},
            ).data,
            message="Folder created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        folder_id, error_response = get_folder_id_param(request)
        if error_response:
            return error_response
        folder = get_folder_queryset(request.user).filter(pk=folder_id).first()
        if not folder:
            return api_error(
                "Folder not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = FolderWriteSerializer(folder, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            folder = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "A folder with this name already exists.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        folder = get_folder_queryset(request.user).get(pk=folder.pk)
        file_counts = build_file_counts(request.user)
        return api_success(
            data=FolderSerializer(
                folder,
                context={"request": request, "file_counts": file_counts},
            ).data,
            message="Folder updated successfully.",
        )

    def delete(self, request):
        folder_id, error_response = get_folder_id_param(request)
        if error_response:
            return error_response
        folder = get_folder_queryset(request.user).filter(pk=folder_id).first()
        if not folder:
            return api_error(
                "Folder not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        folder.delete()
        return api_success(message="Folder deleted successfully.")


class FolderFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_folder_queryset(request.user)
        data = {
            "title": "New Folder",
            "placeholder": "Folder name",
            "fields": {
                "name": {
                    "label": "Folder name",
                    "required": True,
                    "placeholder": "Folder name",
                }
            },
            "actions": [
                {
                    "key": "create",
                    "label": "Create",
                    "path": "/api/folders/",
                }
            ],
            "counts": {"all": queryset.count()},
            "create_path": "/api/folders/",
        }
        if any(key in request.query_params for key in FOLDER_ID_KEYS):
            folder_id, error_response = get_folder_id_param(request)
            if error_response:
                return error_response
            folder = queryset.filter(pk=folder_id).first()
            if not folder:
                return api_error(
                    "Folder not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            file_counts = build_file_counts(request.user)
            data["title"] = "Edit Folder"
            data["folder"] = FolderSerializer(
                folder,
                context={"request": request, "file_counts": file_counts},
            ).data
        return api_success(data=data)


class FolderOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_folder_queryset(request.user)
        return api_success(
            data={
                "title": "Folders",
                "search_placeholder": "Search folders",
                "counts": {"all": queryset.count()},
                "sort_fields": [
                    {"key": "name", "label": "Name"},
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "file_count", "label": "Files"},
                ],
                "default_sort": {"sort_by": "name", "sort_order": "asc"},
                "form_path": "/api/folders/form/",
                "actions": [
                    {
                        "key": "create",
                        "label": "New Folder",
                        "path": "/api/folders/",
                    }
                ],
            }
        )
