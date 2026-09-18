from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.dashboard.periods import PERIOD_CHOICES, PERIOD_LABELS
from apps.organizations.models import Organization
from apps.reports.catalog import catalog_payload, get_report_meta
from apps.reports.services import run_report


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


class ReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        key_present = any(
            name in request.query_params for name in ("report_key", "key", "id")
        )
        report_key = (
            request.query_params.get("report_key")
            or request.query_params.get("key")
            or request.query_params.get("id")
            or ""
        )
        report_key = str(report_key).strip()
        if key_present and not report_key:
            return api_error(
                "report_key is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if report_key:
            meta = get_report_meta(report_key)
            if not meta:
                return api_error(
                    "Report not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            organization = resolve_organization(
                request.user,
                request.query_params.get("organization_id"),
            )
            if not organization:
                return api_error(
                    "Organization not found. Complete organization setup first.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            period = request.query_params.get("period") or "this_fiscal_year"
            data = run_report(organization, meta["key"], period)
            data["key"] = meta["key"]
            data["label"] = meta["label"]
            data["section"] = meta["section"]
            data["section_label"] = meta["section_label"]
            data["title"] = meta["label"]
            return api_success(data=data)

        data = catalog_payload(request.query_params.get("search"))
        return api_success(data=data)


class ReportOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        catalog = catalog_payload()
        return api_success(
            data={
                "title": "Reports",
                "periods": [
                    {"key": key, "label": PERIOD_LABELS[key]} for key in PERIOD_CHOICES
                ],
                "default_period": "this_fiscal_year",
                "groups": catalog["groups"],
                "form_path": "/api/reports/form/",
            }
        )


class ReportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        catalog = catalog_payload()
        return api_success(
            data={
                "title": "Reports",
                "fields": {
                    "report_key": {"label": "Report", "required": True},
                    "period": {
                        "label": "Period",
                        "required": False,
                        "default": "this_fiscal_year",
                    },
                },
                "periods": [
                    {"key": key, "label": PERIOD_LABELS[key]} for key in PERIOD_CHOICES
                ],
                "groups": catalog["groups"],
            }
        )
