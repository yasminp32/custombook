from datetime import date
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
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.manual_journals.filters import (
    MANUAL_JOURNAL_STATUS_FILTERS,
    MANUAL_JOURNAL_TAB_FILTERS,
    ManualJournalFilter,
)
from apps.manual_journals.models import ManualJournal
from apps.manual_journals.serializers import (
    ManualJournalSerializer,
    ManualJournalWriteSerializer,
    next_journal_number,
)

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "journal_date",
    "journal_date": "journal_date",
    "journal#": "journal_number",
    "journal_number": "journal_number",
    "amount": "amount",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_journal_queryset(user):
    return ManualJournal.objects.filter(organization__owner=user).select_related(
        "organization",
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


def get_journal_id_param(request):
    journal_id = (
        request.query_params.get("journal_id")
        or request.query_params.get("manual_journal_id")
        or request.query_params.get("id")
        or request.data.get("journal_id")
        or request.data.get("manual_journal_id")
        or request.data.get("id")
    )
    if not journal_id:
        return None, api_error(
            "journal_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(journal_id, "journal_id")


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


def filtered_journal_queryset(request):
    queryset = get_journal_queryset(request.user)
    journal_filter = ManualJournalFilter(request.query_params, queryset=queryset)
    if not journal_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=journal_filter.errors)
    queryset, error_response = apply_sorting(journal_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def journal_counts(queryset):
    return {
        "all": queryset.count(),
        "draft": queryset.filter(status=ManualJournal.Status.DRAFT).count(),
        "published": queryset.filter(status=ManualJournal.Status.PUBLISHED).count(),
    }


def success_message(journal):
    if journal.status == ManualJournal.Status.PUBLISHED:
        return "Manual journal saved as published."
    return "Manual journal saved as draft."


def build_journal_form(user, organization):
    queryset = get_journal_queryset(user)
    today = date.today()
    next_number = next_journal_number(organization)
    currency = (organization.currency if organization else "INR") or "INR"
    return {
        "title": "New Manual Journal",
        "next_journal_number": next_number,
        "defaults": {
            "journal_number": next_number,
            "journal_date": today.isoformat(),
            "journal_date_label": today.strftime("%d %b %Y"),
            "reference_number": "",
            "amount": "0.00",
            "currency": currency,
            "status": ManualJournal.Status.DRAFT,
            "action": "save_as_draft",
            "notes": "",
        },
        "fields": {
            "journal_number": {"label": "Journal#", "required": True},
            "reference_number": {
                "label": "Reference#",
                "required": False,
                "placeholder": "Enter reference",
            },
            "journal_date": {"label": "Journal Date", "required": True},
            "amount": {"label": "Amount (₹)", "required": True},
            "notes": {"label": "Notes", "required": False, "placeholder": "Add notes"},
        },
        "counts": journal_counts(queryset),
        "actions": [
            {
                "key": "save_as_draft",
                "label": "Save as Draft",
                "path": "/api/manual-journals/",
            },
            {
                "key": "save_as_published",
                "label": "Save as Published",
                "path": "/api/manual-journals/",
            },
        ],
        "create_path": "/api/manual-journals/",
        "export_path": "/api/manual-journals/export/",
        "refresh_path": "/api/manual-journals/refresh/",
    }


class ManualJournalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if any(
            key in request.query_params
            for key in ("journal_id", "manual_journal_id", "id")
        ):
            journal_id = (
                request.query_params.get("journal_id")
                or request.query_params.get("manual_journal_id")
                or request.query_params.get("id")
            )
            parsed_id, error_response = parse_uuid(journal_id, "journal_id")
            if error_response:
                return error_response
            journal = get_journal_queryset(request.user).filter(pk=parsed_id).first()
            if not journal:
                return api_error(
                    "Manual journal not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return api_success(data=ManualJournalSerializer(journal).data)

        queryset, error_response = filtered_journal_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=ManualJournalSerializer)
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
        serializer = ManualJournalWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            journal = serializer.save(
                organization=organization,
                created_by=request.user,
            )
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Journal number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        journal = get_journal_queryset(request.user).get(pk=journal.pk)
        return api_success(
            data=ManualJournalSerializer(journal).data,
            message=success_message(journal),
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        journal_id, error_response = get_journal_id_param(request)
        if error_response:
            return error_response
        journal = get_journal_queryset(request.user).filter(pk=journal_id).first()
        if not journal:
            return api_error(
                "Manual journal not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = ManualJournalWriteSerializer(
            journal,
            data=request.data,
            partial=partial,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            journal = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        except IntegrityError:
            return api_error(
                "Journal number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        journal = get_journal_queryset(request.user).get(pk=journal.pk)
        return api_success(
            data=ManualJournalSerializer(journal).data,
            message="Manual journal updated successfully.",
        )

    def delete(self, request):
        journal_id, error_response = get_journal_id_param(request)
        if error_response:
            return error_response
        journal = get_journal_queryset(request.user).filter(pk=journal_id).first()
        if not journal:
            return api_error(
                "Manual journal not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if journal.status == ManualJournal.Status.PUBLISHED:
            return api_error(
                "Published journals cannot be deleted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        journal.delete()
        return api_success(message="Manual journal deleted successfully.")


class ManualJournalOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_journal_queryset(request.user)
        return api_success(
            data={
                "title": "Manual Journals",
                "tabs": [
                    {"key": key, "label": label} for key, label in MANUAL_JOURNAL_TAB_FILTERS
                ],
                "statuses": [
                    {"key": key, "label": label}
                    for key, label in MANUAL_JOURNAL_STATUS_FILTERS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "journal_number", "label": "Journal#"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/manual-journals/form/",
                "counts": journal_counts(queryset),
                "actions": [
                    {
                        "key": "save_as_draft",
                        "label": "Save as Draft",
                        "path": "/api/manual-journals/",
                    },
                    {
                        "key": "save_as_published",
                        "label": "Save as Published",
                        "path": "/api/manual-journals/",
                    },
                    {
                        "key": "export",
                        "label": "Export Journals",
                        "description": "Export the current manual journal list",
                        "path": "/api/manual-journals/export/",
                    },
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "description": "Reload the latest manual journals",
                        "path": "/api/manual-journals/refresh/",
                    },
                    {
                        "key": "publish",
                        "label": "Save as Published",
                        "path": "/api/manual-journals/publish/",
                    },
                ],
            }
        )


class ManualJournalFormView(APIView):
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
        data = build_journal_form(request.user, organization)
        journal_id = (
            request.query_params.get("journal_id")
            or request.query_params.get("manual_journal_id")
            or request.query_params.get("id")
        )
        if journal_id:
            parsed_id, error_response = parse_uuid(journal_id, "journal_id")
            if error_response:
                return error_response
            journal = get_journal_queryset(request.user).filter(pk=parsed_id).first()
            if not journal:
                return api_error(
                    "Manual journal not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            data["title"] = "Edit Manual Journal"
            data["journal"] = ManualJournalSerializer(journal).data
        return api_success(data=data)


class ManualJournalRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_journal_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=ManualJournalSerializer)
        if response is not None:
            response.data["message"] = "Manual journals refreshed."
            return response
        return api_success(data=[], message="Manual journals refreshed.")


class ManualJournalExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_journal_queryset(request)
        if error_response:
            return error_response
        rows = ManualJournalSerializer(queryset, many=True).data
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
                    "journal_id",
                    "journal_number",
                    "reference_number",
                    "journal_date",
                    "status",
                    "amount",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "journal_id": row["journal_id"],
                        "journal_number": row["journal_number"],
                        "reference_number": row["reference_number"],
                        "journal_date": row["journal_date"],
                        "status": row["status"],
                        "amount": row["amount"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="manual_journals.csv"'
            return response
        return api_success(
            data={"count": len(rows), "journals": rows},
            message="Manual journals exported successfully.",
        )


class ManualJournalPublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        journal_id, error_response = get_journal_id_param(request)
        if error_response:
            return error_response
        journal = get_journal_queryset(request.user).filter(pk=journal_id).first()
        if not journal:
            return api_error(
                "Manual journal not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if journal.status == ManualJournal.Status.PUBLISHED:
            return api_error(
                "This journal is already published.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        journal.status = ManualJournal.Status.PUBLISHED
        if not journal.published_at:
            journal.published_at = timezone.now()
        journal.save(update_fields=["status", "published_at", "updated_at"])
        journal = get_journal_queryset(request.user).get(pk=journal.pk)
        return api_success(
            data=ManualJournalSerializer(journal).data,
            message="Manual journal saved as published.",
        )
