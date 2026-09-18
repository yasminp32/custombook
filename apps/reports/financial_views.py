import csv
import io

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.reports.financial import (
    BUILDERS,
    COMPARE_WITH_CHOICES,
    DATE_RANGE_CHOICES,
    FILTER_ACCOUNTS_CHOICES,
    FINANCIAL_REPORTS,
    REPORT_BASIS_CHOICES,
    default_export_options,
    export_form_payload,
    form_payload,
)
from apps.reports.pdf import build_financial_pdf


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_organization_id(request):
    if "organization_id" in request.query_params:
        return request.query_params.get("organization_id")
    body = body_data(request)
    if "organization_id" in body:
        return body.get("organization_id")
    return None


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id is not None and str(organization_id).strip() == "":
        return None, api_error(
            "organization_id is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id), None
    organization = organizations.order_by("created_at").first()
    if not organization:
        return None, api_error(
            "Organization not found. Complete organization setup first.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return organization, None


def body_data(request):
    if request.method in ("POST", "PUT", "PATCH"):
        data = getattr(request, "data", None)
        if isinstance(data, dict):
            return data
    return {}


def request_filters(request):
    data = {}
    data.update(request.query_params.dict())
    data.update(body_data(request))
    data.pop("export_format", None)
    data.pop("export_options", None)
    return data


def merge_export_options(request):
    options = default_export_options()
    payload = {}
    payload.update(request.query_params.dict())
    payload.update(body_data(request))
    nested = payload.get("export_options")
    if isinstance(nested, dict):
        payload.update(nested)
    display = dict(options["display"])
    incoming_display = payload.get("display")
    if isinstance(incoming_display, dict):
        for key in display:
            if key in incoming_display:
                display[key] = bool(incoming_display[key])
    margins = dict(options["margins"])
    incoming_margins = payload.get("margins")
    if isinstance(incoming_margins, dict):
        for key in margins:
            if incoming_margins.get(key) not in (None, ""):
                margins[key] = str(incoming_margins[key])
    options.update(
        {
            "export_file_name": payload.get("export_file_name") or options["export_file_name"],
            "password_protect": str(payload.get("password_protect", "")).lower()
            in ("1", "true", "yes")
            or payload.get("password_protect") is True,
            "password": payload.get("password") or "",
            "language": payload.get("language") or "en",
            "display": display,
            "column_headers_on_each_page": str(
                payload.get("column_headers_on_each_page", True)
            ).lower()
            not in ("0", "false", "no"),
            "temporary_note": payload.get("temporary_note") or "",
            "table_density": payload.get("table_density") or "classic",
            "auto_resize_table": str(payload.get("auto_resize_table", True)).lower()
            not in ("0", "false", "no"),
            "paper_size": payload.get("paper_size") or "A4",
            "orientation": payload.get("orientation") or "portrait",
            "margins": margins,
        }
    )
    return options


def run_financial_report(organization, report_key, filters):
    builder = BUILDERS[report_key]
    return builder(organization, filters)


def csv_response(report, filename):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    headers = ["Account", "Total"]
    if any(col.get("key") == "compare" for col in report.get("columns") or []):
        headers.append("Compare")
    writer.writerow(headers)
    for row in report.get("rows") or []:
        indent = "  " * int(row.get("depth") or 0)
        line = [f"{indent}{row.get('label')}", row.get("amount_display") or row.get("amount")]
        if len(headers) > 2:
            line.append(row.get("compare_amount_display") or row.get("compare_amount") or "")
        writer.writerow(line)
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    return response


def pdf_response(report, export_options, generated_by, filename):
    content = build_financial_pdf(report, export_options, generated_by=generated_by)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response


def export_filename(report, export_options):
    name = (export_options.get("export_file_name") or report.get("title") or "report").strip()
    name = "".join(ch if ch.isalnum() or ch in ("-", "_", " ") else "_" for ch in name)
    return name.replace(" ", "_") or "report"


class FinancialReportIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Financial Reports",
                "reports": list(FINANCIAL_REPORTS),
            }
        )


class FinancialReportOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Financial Reports",
                "reports": list(FINANCIAL_REPORTS),
                "report_basis": list(REPORT_BASIS_CHOICES),
                "filter_accounts": list(FILTER_ACCOUNTS_CHOICES),
                "compare_with": list(COMPARE_WITH_CHOICES),
                "date_range": list(DATE_RANGE_CHOICES),
                "default_basis": "cash",
                "default_filter_accounts": "without_zero_balance",
                "default_compare_with": "none",
            }
        )


class FinancialRunView(APIView):
    permission_classes = [IsAuthenticated]
    report_key = None

    def get(self, request, *args, **kwargs):
        return self._run(request)

    def post(self, request, *args, **kwargs):
        return self._run(request)

    def _run(self, request):
        organization, error = resolve_organization(
            request.user,
            get_organization_id(request),
        )
        if error:
            return error
        data = run_financial_report(organization, self.report_key, request_filters(request))
        return api_success(data=data)


class FinancialFormView(APIView):
    permission_classes = [IsAuthenticated]
    report_key = None

    def get(self, request):
        return api_success(data=form_payload(self.report_key))


class FinancialOptionsView(APIView):
    permission_classes = [IsAuthenticated]
    report_key = None

    def get(self, request):
        data = form_payload(self.report_key)
        data["export_form"] = export_form_payload(self.report_key)
        return api_success(data=data)


class FinancialExportFormView(APIView):
    permission_classes = [IsAuthenticated]
    report_key = None

    def get(self, request):
        return api_success(data=export_form_payload(self.report_key))


class FinancialExportView(APIView):
    permission_classes = [IsAuthenticated]
    report_key = None

    def get(self, request, *args, **kwargs):
        return self._export(request)

    def post(self, request, *args, **kwargs):
        return self._export(request)

    def _export(self, request):
        organization, error = resolve_organization(
            request.user,
            get_organization_id(request),
        )
        if error:
            return error
        export_options = merge_export_options(request)
        if export_options["password_protect"] and not str(export_options["password"]).strip():
            return api_error(
                "Password is required when protecting the exported file.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        report = run_financial_report(organization, self.report_key, request_filters(request))
        export_format = (
            request.query_params.get("export_format")
            or body_data(request).get("export_format")
            or "pdf"
        ).strip().lower()
        filename = export_filename(report, export_options)
        if export_format == "csv":
            return csv_response(report, filename)
        if export_format == "json":
            return api_success(
                data={
                    "filename": f"{filename}.json",
                    "export_options": export_options,
                    "report": report,
                }
            )
        generated_by = getattr(request.user, "email", "") or ""
        return pdf_response(report, export_options, generated_by, filename)


class BalanceSheetView(FinancialRunView):
    report_key = "balance_sheet"


class BalanceSheetOptionsView(FinancialOptionsView):
    report_key = "balance_sheet"


class BalanceSheetFormView(FinancialFormView):
    report_key = "balance_sheet"


class BalanceSheetExportFormView(FinancialExportFormView):
    report_key = "balance_sheet"


class BalanceSheetExportView(FinancialExportView):
    report_key = "balance_sheet"


class ProfitAndLossView(FinancialRunView):
    report_key = "profit_and_loss"


class ProfitAndLossOptionsView(FinancialOptionsView):
    report_key = "profit_and_loss"


class ProfitAndLossFormView(FinancialFormView):
    report_key = "profit_and_loss"


class ProfitAndLossExportFormView(FinancialExportFormView):
    report_key = "profit_and_loss"


class ProfitAndLossExportView(FinancialExportView):
    report_key = "profit_and_loss"


class CashFlowStatementView(FinancialRunView):
    report_key = "cash_flow_statement"


class CashFlowStatementOptionsView(FinancialOptionsView):
    report_key = "cash_flow_statement"


class CashFlowStatementFormView(FinancialFormView):
    report_key = "cash_flow_statement"


class CashFlowStatementExportFormView(FinancialExportFormView):
    report_key = "cash_flow_statement"


class CashFlowStatementExportView(FinancialExportView):
    report_key = "cash_flow_statement"
