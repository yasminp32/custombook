from datetime import date
from uuid import UUID

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.projects.models import Project
from apps.time_entries.models import TimeEntry
from apps.time_entries.serializers import TimeEntrySerializer
from apps.timer.models import DEFAULT_TASKS, TimerSession
from apps.timer.serializers import TimerSerializer, TimerWriteSerializer


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def parse_uuid(value, field_name="id"):
    if value is None or str(value).strip() == "":
        return None, None
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


def get_or_create_timer(user, organization):
    timer, _created = TimerSession.objects.get_or_create(
        organization=organization,
        user=user,
        defaults={"status": TimerSession.Status.PAUSED},
    )
    return TimerSession.objects.select_related("organization", "project", "user").get(
        pk=timer.pk
    )


def apply_timer_fields(timer, data, organization):
    if "task_name" in data:
        timer.task_name = data.get("task_name") or ""
    if "notes" in data:
        timer.notes = data.get("notes") or ""
    if "project_id" in data:
        project_id = data.get("project_id")
        if not project_id:
            timer.project = None
        else:
            project = Project.objects.filter(
                pk=project_id,
                organization=organization,
            ).first()
            if not project:
                return api_error(
                    "Project not found.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            timer.project = project
    return None


def project_option(project):
    return {
        "project_id": project.id,
        "name": project.name,
        "status": project.status,
    }


def task_options(organization, project_id=None):
    names = list(DEFAULT_TASKS)
    queryset = TimeEntry.objects.filter(organization=organization).exclude(task_name="")
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    for name in queryset.order_by("task_name").values_list("task_name", flat=True).distinct():
        if name not in names:
            names.append(name)
    return [{"task_name": name} for name in names]


def timer_payload(timer, organization, request=None):
    data = TimerSerializer(timer).data
    project_id = request.query_params.get("project_id") if request else None
    parsed_project_id = None
    if project_id:
        parsed_project_id, error_response = parse_uuid(project_id, "project_id")
        if error_response:
            return None, error_response
    data["projects"] = [
        project_option(row)
        for row in Project.objects.filter(organization=organization).order_by("name")[:100]
    ]
    data["tasks"] = task_options(organization, parsed_project_id or timer.project_id)
    data["title"] = "Timer"
    data["subtitle"] = "Track your time"
    data["actions"] = [
        {"key": "start", "label": "Start", "path": "/api/timer/start/"},
        {"key": "stop", "label": "Stop", "path": "/api/timer/stop/"},
        {"key": "pause", "label": "Pause", "path": "/api/timer/pause/"},
        {"key": "history", "label": "History", "path": "/api/timer/history/"},
    ]
    return data, None


class TimerView(APIView):
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
        timer = get_or_create_timer(request.user, organization)
        data, error_response = timer_payload(timer, organization, request)
        if error_response:
            return error_response
        return api_success(data=data)

    def patch(self, request):
        organization = resolve_organization(
            request.user,
            request.data.get("organization_id") or request.query_params.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = TimerWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        timer = get_or_create_timer(request.user, organization)
        error_response = apply_timer_fields(timer, serializer.validated_data, organization)
        if error_response:
            return error_response
        timer.save()
        timer = get_or_create_timer(request.user, organization)
        data, error_response = timer_payload(timer, organization)
        if error_response:
            return error_response
        return api_success(data=data, message="Timer updated.")


class TimerFormView(APIView):
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
        timer = get_or_create_timer(request.user, organization)
        data, error_response = timer_payload(timer, organization, request)
        if error_response:
            return error_response
        return api_success(data=data)


class TimerStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization = resolve_organization(
            request.user,
            request.data.get("organization_id") or request.query_params.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = TimerWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        timer = get_or_create_timer(request.user, organization)
        error_response = apply_timer_fields(timer, serializer.validated_data, organization)
        if error_response:
            return error_response
        if timer.status != TimerSession.Status.RUNNING:
            timer.status = TimerSession.Status.RUNNING
            timer.started_at = timezone.now()
        timer.save()
        timer = get_or_create_timer(request.user, organization)
        data, error_response = timer_payload(timer, organization)
        if error_response:
            return error_response
        return api_success(data=data, message="Timer started.")


class TimerPauseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization = resolve_organization(
            request.user,
            request.data.get("organization_id") or request.query_params.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        timer = get_or_create_timer(request.user, organization)
        if timer.status == TimerSession.Status.RUNNING:
            extra = 0
            if timer.started_at:
                extra = int((timezone.now() - timer.started_at).total_seconds())
            timer.accumulated_seconds = max(int(timer.accumulated_seconds or 0) + extra, 0)
            timer.started_at = None
            timer.status = TimerSession.Status.PAUSED
            timer.save(update_fields=["accumulated_seconds", "started_at", "status", "updated_at"])
        timer = get_or_create_timer(request.user, organization)
        data, error_response = timer_payload(timer, organization)
        if error_response:
            return error_response
        return api_success(data=data, message="Timer paused.")


class TimerStopView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization = resolve_organization(
            request.user,
            request.data.get("organization_id") or request.query_params.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = TimerWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        timer = get_or_create_timer(request.user, organization)
        error_response = apply_timer_fields(timer, serializer.validated_data, organization)
        if error_response:
            return error_response
        if timer.status == TimerSession.Status.RUNNING:
            extra = 0
            if timer.started_at:
                extra = int((timezone.now() - timer.started_at).total_seconds())
            timer.accumulated_seconds = max(int(timer.accumulated_seconds or 0) + extra, 0)
            timer.started_at = None
            timer.status = TimerSession.Status.PAUSED
        timer.save()

        if timer.elapsed_seconds() <= 0:
            return api_error(
                "No time recorded. Start the timer first.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not timer.project_id:
            return api_error(
                "Project is required to stop the timer.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not (timer.task_name or "").strip():
            return api_error(
                "Task is required to stop the timer.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        hours, minutes = timer.to_hours_minutes()
        entry = TimeEntry.objects.create(
            organization=organization,
            project=timer.project,
            task_name=timer.task_name.strip(),
            user=request.user,
            created_by=request.user,
            log_date=date.today(),
            hours=hours,
            minutes=minutes,
            notes=timer.notes or "",
            is_billable=True,
        )
        timer.accumulated_seconds = 0
        timer.started_at = None
        timer.status = TimerSession.Status.PAUSED
        timer.save()
        timer = get_or_create_timer(request.user, organization)
        data, error_response = timer_payload(timer, organization)
        if error_response:
            return error_response
        data["time_entry"] = TimeEntrySerializer(entry).data
        return api_success(data=data, message="Timer stopped and time entry saved.")


class TimerHistoryView(APIView):
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
        queryset = TimeEntry.objects.filter(
            organization=organization,
            user=request.user,
        ).select_related("project", "user", "organization").order_by("-log_date", "-created_at")
        response = paginate_queryset(request, queryset, serializer=TimeEntrySerializer)
        if response is not None:
            return response
        return api_success(data=[])
