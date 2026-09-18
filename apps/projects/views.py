from uuid import UUID

from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as SerializerValidationError
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.customers.models import Customer
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.projects.filters import (
    PROJECT_STATUS_FILTERS,
    PROJECT_TAB_FILTERS,
    ProjectFilter,
)
from apps.projects.models import Project
from apps.projects.serializers import ProjectSerializer, ProjectWriteSerializer

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "project_name": "name",
    "name": "name",
    "customer_name": "customer__display_name",
    "rate": "rate",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_project_queryset(user):
    return Project.objects.filter(organization__owner=user).select_related(
        "organization",
        "customer",
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


def get_project_id_param(request):
    project_id = (
        request.query_params.get("project_id")
        or request.query_params.get("id")
        or request.data.get("project_id")
        or request.data.get("id")
    )
    if not project_id:
        return None, api_error(
            "project_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(project_id, "project_id")


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


def filtered_project_queryset(request):
    queryset = get_project_queryset(request.user)
    project_filter = ProjectFilter(request.query_params, queryset=queryset)
    if not project_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=project_filter.errors)
    queryset, error_response = apply_sorting(project_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def project_counts(queryset):
    return {
        "all": queryset.count(),
        "active": queryset.filter(status=Project.Status.ACTIVE).count(),
        "completed": queryset.filter(status=Project.Status.COMPLETED).count(),
        "on_hold": queryset.filter(status=Project.Status.ON_HOLD).count(),
        "cancelled": queryset.filter(status=Project.Status.CANCELLED).count(),
    }


def customer_option(customer):
    name = customer.display_name or customer.company_name or customer.name
    return {
        "customer_id": customer.id,
        "display_name": name,
        "company_name": customer.company_name or "",
        "initials": (name[:1] or "").upper(),
    }


def success_message(project):
    if project.status == Project.Status.COMPLETED:
        return "Project marked as completed."
    if project.status == Project.Status.ON_HOLD:
        return "Project put on hold."
    if project.status == Project.Status.CANCELLED:
        return "Project cancelled."
    return "Project saved."


def build_project_form(user, organization):
    queryset = get_project_queryset(user)
    customers = Customer.objects.filter(
        organization=organization,
        status=Customer.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    currency = (organization.currency if organization else "INR") or "INR"
    return {
        "title": "New Project",
        "defaults": {
            "name": "",
            "billing_method": Project.BillingMethod.FIXED_COST,
            "rate": "0.00",
            "budget_hours": "0",
            "currency": currency,
            "status": Project.Status.ACTIVE,
            "action": "save",
        },
        "fields": {
            "name": {
                "label": "Project Name",
                "required": True,
                "placeholder": "Enter project name",
            },
            "customer_id": {
                "label": "Customer Name",
                "required": True,
                "placeholder": "Select a Customer",
            },
            "billing_method": {
                "label": "Billing Method",
                "required": False,
            },
            "rate": {"label": "Rate (₹)", "required": False},
            "budget_hours": {"label": "Budget Hours", "required": False},
        },
        "customers": [customer_option(row) for row in customers],
        "billing_methods": [
            {"key": key, "label": label} for key, label in Project.BillingMethod.choices
        ],
        "counts": project_counts(queryset),
        "actions": [
            {"key": "save", "label": "Save", "path": "/api/projects/"},
        ],
        "create_path": "/api/projects/",
        "export_path": "/api/projects/export/",
        "refresh_path": "/api/projects/refresh/",
    }


class ProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project_id") or request.query_params.get("id")
        if project_id:
            parsed_id, error_response = parse_uuid(project_id, "project_id")
            if error_response:
                return error_response
            project = get_project_queryset(request.user).filter(pk=parsed_id).first()
            if not project:
                return api_error("Project not found.", status_code=status.HTTP_404_NOT_FOUND)
            return api_success(data=ProjectSerializer(project).data)

        queryset, error_response = filtered_project_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=ProjectSerializer)
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
        serializer = ProjectWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            project = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Could not save project.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        project = get_project_queryset(request.user).get(pk=project.pk)
        return api_success(
            data=ProjectSerializer(project).data,
            message=success_message(project),
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        project_id, error_response = get_project_id_param(request)
        if error_response:
            return error_response
        project = get_project_queryset(request.user).filter(pk=project_id).first()
        if not project:
            return api_error("Project not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = ProjectWriteSerializer(project, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            project = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Could not save project.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        project = get_project_queryset(request.user).get(pk=project.pk)
        return api_success(
            data=ProjectSerializer(project).data,
            message="Project updated successfully.",
        )

    def delete(self, request):
        project_id, error_response = get_project_id_param(request)
        if error_response:
            return error_response
        project = get_project_queryset(request.user).filter(pk=project_id).first()
        if not project:
            return api_error("Project not found.", status_code=status.HTTP_404_NOT_FOUND)
        if project.status == Project.Status.COMPLETED:
            return api_error(
                "Completed projects cannot be deleted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        project.delete()
        return api_success(message="Project deleted successfully.")


class ProjectOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_project_queryset(request.user)
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in PROJECT_TAB_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in PROJECT_STATUS_FILTERS
                ],
                "billing_methods": [
                    {"key": key, "label": label} for key, label in Project.BillingMethod.choices
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "project_name", "label": "Project Name"},
                    {"key": "customer_name", "label": "Customer Name"},
                    {"key": "rate", "label": "Rate"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/projects/form/",
                "counts": project_counts(queryset),
                "actions": [
                    {"key": "save", "label": "Save", "path": "/api/projects/"},
                    {
                        "key": "export",
                        "label": "Export Projects",
                        "description": "Export the current project list",
                        "path": "/api/projects/export/",
                    },
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "description": "Reload the latest projects",
                        "path": "/api/projects/refresh/",
                    },
                    {
                        "key": "mark_completed",
                        "label": "Mark as Completed",
                        "path": "/api/projects/mark-completed/",
                    },
                    {
                        "key": "mark_on_hold",
                        "label": "Mark as On Hold",
                        "path": "/api/projects/mark-on-hold/",
                    },
                    {
                        "key": "cancel",
                        "label": "Cancel",
                        "path": "/api/projects/cancel/",
                    },
                ],
            }
        )


class ProjectFormView(APIView):
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
        data = build_project_form(request.user, organization)
        project_id = request.query_params.get("project_id") or request.query_params.get("id")
        if project_id:
            parsed_id, error_response = parse_uuid(project_id, "project_id")
            if error_response:
                return error_response
            project = get_project_queryset(request.user).filter(pk=parsed_id).first()
            if not project:
                return api_error("Project not found.", status_code=status.HTTP_404_NOT_FOUND)
            data["title"] = "Edit Project"
            data["project"] = ProjectSerializer(project).data
        return api_success(data=data)


class ProjectRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_project_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=ProjectSerializer)
        if response is not None:
            response.data["message"] = "Projects refreshed."
            return response
        return api_success(data=[], message="Projects refreshed.")


class ProjectExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_project_queryset(request)
        if error_response:
            return error_response
        rows = ProjectSerializer(queryset, many=True).data
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
                    "project_id",
                    "name",
                    "customer_name",
                    "billing_method",
                    "rate",
                    "budget_hours",
                    "amount",
                    "status",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "project_id": row["project_id"],
                        "name": row["name"],
                        "customer_name": row["customer_name"],
                        "billing_method": row["billing_method"],
                        "rate": row["rate"],
                        "budget_hours": row["budget_hours"],
                        "amount": row["amount"],
                        "status": row["status"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="projects.csv"'
            return response
        return api_success(
            data={"count": len(rows), "projects": rows},
            message="Projects exported successfully.",
        )


def _set_project_status(request, allowed_statuses, new_status, timestamp_field, message):
    project_id, error_response = get_project_id_param(request)
    if error_response:
        return error_response
    project = get_project_queryset(request.user).filter(pk=project_id).first()
    if not project:
        return api_error("Project not found.", status_code=status.HTTP_404_NOT_FOUND)
    if project.status not in allowed_statuses:
        return api_error(message, status_code=status.HTTP_400_BAD_REQUEST)
    project.status = new_status
    update_fields = ["status", "updated_at"]
    if timestamp_field and not getattr(project, timestamp_field):
        setattr(project, timestamp_field, timezone.now())
        update_fields.append(timestamp_field)
    project.save(update_fields=update_fields)
    project = get_project_queryset(request.user).get(pk=project.pk)
    return project


class ProjectMarkCompletedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = _set_project_status(
            request,
            (Project.Status.ACTIVE,),
            Project.Status.COMPLETED,
            "completed_at",
            "Only active projects can be marked as completed.",
        )
        if not isinstance(result, Project):
            return result
        return api_success(
            data=ProjectSerializer(result).data,
            message="Project marked as completed.",
        )


class ProjectMarkOnHoldView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = _set_project_status(
            request,
            (Project.Status.ACTIVE,),
            Project.Status.ON_HOLD,
            "on_hold_at",
            "Only active projects can be put on hold.",
        )
        if not isinstance(result, Project):
            return result
        return api_success(
            data=ProjectSerializer(result).data,
            message="Project put on hold.",
        )


class ProjectCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = _set_project_status(
            request,
            (Project.Status.ACTIVE, Project.Status.ON_HOLD),
            Project.Status.CANCELLED,
            "cancelled_at",
            "Only active or on-hold projects can be cancelled.",
        )
        if not isinstance(result, Project):
            return result
        return api_success(
            data=ProjectSerializer(result).data,
            message="Project cancelled.",
        )
