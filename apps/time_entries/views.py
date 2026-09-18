from datetime import date
from uuid import UUID

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as SerializerValidationError
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.projects.models import Project
from apps.time_entries.filters import (
    TIME_ENTRY_TAB_FILTERS,
    TIME_ENTRY_TYPE_FILTERS,
    TimeEntryFilter,
)
from apps.time_entries.models import TimeEntry
from apps.time_entries.serializers import (
    TimeEntrySerializer,
    TimeEntryWriteSerializer,
    user_display_name,
)

User = get_user_model()

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "log_date",
    "log_date": "log_date",
    "project_name": "project__name",
    "duration": "duration_minutes",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_time_entry_queryset(user):
    return TimeEntry.objects.filter(organization__owner=user).select_related(
        "organization",
        "project",
        "user",
        "created_by",
    )


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


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


def get_time_entry_id_param(request):
    time_entry_id = (
        request.query_params.get("time_entry_id")
        or request.query_params.get("id")
        or request.data.get("time_entry_id")
        or request.data.get("id")
    )
    if not time_entry_id:
        return None, api_error(
            "time_entry_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(time_entry_id, "time_entry_id")


def apply_sorting(queryset, query_params):
    sort_by = (query_params.get("sort_by") or "created_time").strip().lower()
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


def filtered_time_entry_queryset(request):
    queryset = get_time_entry_queryset(request.user)
    time_filter = TimeEntryFilter(request.query_params, queryset=queryset)
    if not time_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=time_filter.errors)
    queryset, error_response = apply_sorting(time_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def time_entry_counts(queryset):
    return {
        "all": queryset.count(),
        "billable": queryset.filter(is_billable=True).count(),
        "non_billable": queryset.filter(is_billable=False).count(),
    }


def project_option(project):
    customer_name = ""
    if project.customer:
        customer_name = (
            project.customer.display_name
            or project.customer.company_name
            or project.customer.name
        )
    return {
        "project_id": project.id,
        "name": project.name,
        "status": project.status,
        "customer_name": customer_name,
    }


def user_option(user, organization):
    name = user_display_name(user, organization)
    return {
        "user_id": user.id,
        "display_name": name,
        "email": user.email,
        "initials": (name[:1] or "").upper(),
        "is_owner": user.id == organization.owner_id,
    }


def build_time_entry_form(user, organization):
    queryset = get_time_entry_queryset(user)
    projects = Project.objects.filter(organization=organization).order_by("name")[:100]
    today = date.today()
    users = []
    seen = set()
    for candidate in (organization.owner, user):
        if candidate and candidate.id not in seen:
            users.append(user_option(candidate, organization))
            seen.add(candidate.id)
    return {
        "title": "New Time Entry",
        "defaults": {
            "task_name": "",
            "user_id": user.id,
            "log_date": today.isoformat(),
            "log_date_label": today.strftime("%d %b %Y"),
            "hours": 0,
            "minutes": 0,
            "is_billable": True,
            "type": "billable",
            "notes": "",
            "action": "save",
        },
        "fields": {
            "project_id": {
                "label": "Project",
                "required": True,
                "placeholder": "Select a Project",
            },
            "task_name": {
                "label": "Task Name",
                "required": True,
                "placeholder": "Enter task name",
            },
            "user_id": {"label": "User", "required": False},
            "log_date": {"label": "Log Date", "required": True},
            "hours": {"label": "Hours", "required": False},
            "minutes": {"label": "Minutes", "required": False},
            "is_billable": {"label": "Billable", "required": False},
            "notes": {"label": "Notes", "required": False, "placeholder": "Add notes"},
        },
        "projects": [project_option(row) for row in projects],
        "users": users,
        "types": [
            {"key": "billable", "label": "Billable"},
            {"key": "non_billable", "label": "Non-billable"},
        ],
        "counts": time_entry_counts(queryset),
        "actions": [
            {"key": "save", "label": "Save", "path": "/api/time-entries/"},
        ],
        "create_path": "/api/time-entries/",
        "export_path": "/api/time-entries/export/",
        "refresh_path": "/api/time-entries/refresh/",
    }


class TimeEntryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        time_entry_id = (
            request.query_params.get("time_entry_id") or request.query_params.get("id")
        )
        if time_entry_id:
            parsed_id, error_response = parse_uuid(time_entry_id, "time_entry_id")
            if error_response:
                return error_response
            entry = get_time_entry_queryset(request.user).filter(pk=parsed_id).first()
            if not entry:
                return api_error(
                    "Time entry not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return api_success(data=TimeEntrySerializer(entry).data)

        queryset, error_response = filtered_time_entry_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=TimeEntrySerializer)
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
        serializer = TimeEntryWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            entry = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        entry = get_time_entry_queryset(request.user).get(pk=entry.pk)
        return api_success(
            data=TimeEntrySerializer(entry).data,
            message="Time entry saved.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        time_entry_id, error_response = get_time_entry_id_param(request)
        if error_response:
            return error_response
        entry = get_time_entry_queryset(request.user).filter(pk=time_entry_id).first()
        if not entry:
            return api_error("Time entry not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = TimeEntryWriteSerializer(entry, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            entry = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        entry = get_time_entry_queryset(request.user).get(pk=entry.pk)
        return api_success(
            data=TimeEntrySerializer(entry).data,
            message="Time entry updated successfully.",
        )

    def delete(self, request):
        time_entry_id, error_response = get_time_entry_id_param(request)
        if error_response:
            return error_response
        entry = get_time_entry_queryset(request.user).filter(pk=time_entry_id).first()
        if not entry:
            return api_error("Time entry not found.", status_code=status.HTTP_404_NOT_FOUND)
        entry.delete()
        return api_success(message="Time entry deleted successfully.")


class TimeEntryOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_time_entry_queryset(request.user)
        return api_success(
            data={
                "tabs": [
                    {"key": key, "label": label} for key, label in TIME_ENTRY_TAB_FILTERS
                ],
                "types": [
                    {"key": key, "label": label} for key, label in TIME_ENTRY_TYPE_FILTERS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "project_name", "label": "Project Name"},
                    {"key": "duration", "label": "Duration"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "search_placeholder": "Search by task, project or user",
                "form_path": "/api/time-entries/form/",
                "counts": time_entry_counts(queryset),
                "actions": [
                    {"key": "save", "label": "Save", "path": "/api/time-entries/"},
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "path": "/api/time-entries/refresh/",
                    },
                    {
                        "key": "export",
                        "label": "Export Time Entries",
                        "path": "/api/time-entries/export/",
                    },
                ],
            }
        )


class TimeEntryFormView(APIView):
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
        data = build_time_entry_form(request.user, organization)
        time_entry_id = (
            request.query_params.get("time_entry_id") or request.query_params.get("id")
        )
        if time_entry_id:
            parsed_id, error_response = parse_uuid(time_entry_id, "time_entry_id")
            if error_response:
                return error_response
            entry = get_time_entry_queryset(request.user).filter(pk=parsed_id).first()
            if not entry:
                return api_error(
                    "Time entry not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            data["title"] = "Edit Time Entry"
            data["time_entry"] = TimeEntrySerializer(entry).data
        return api_success(data=data)


class TimeEntryRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_time_entry_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=TimeEntrySerializer)
        if response is not None:
            response.data["message"] = "Time entries refreshed."
            return response
        return api_success(data=[], message="Time entries refreshed.")


class TimeEntryExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_time_entry_queryset(request)
        if error_response:
            return error_response
        rows = TimeEntrySerializer(queryset, many=True).data
        export_format = (
            request.query_params.get("export_format")
            or request.query_params.get("format")
            or "json"
        ).strip().lower()
        if export_format == "csv":
            import csv
            from io import StringIO

            buffer = StringIO()
            writer = csv.DictWriter(
                buffer,
                fieldnames=[
                    "time_entry_id",
                    "task_name",
                    "project_name",
                    "user_name",
                    "log_date",
                    "duration_label",
                    "type",
                    "notes",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "time_entry_id": row["time_entry_id"],
                        "task_name": row["task_name"],
                        "project_name": row["project_name"],
                        "user_name": row["user_name"],
                        "log_date": row["log_date"],
                        "duration_label": row["duration_label"],
                        "type": row["type"],
                        "notes": row["notes"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="time_entries.csv"'
            return response
        return api_success(
            data={"count": len(rows), "time_entries": rows},
            message="Time entries exported successfully.",
        )
