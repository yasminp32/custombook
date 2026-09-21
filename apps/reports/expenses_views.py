import csv
import io

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.reports.expenses import (
    EXPENSE_REPORTS,
    build_expenses_by_category_report,
    expenses_by_category_form_payload,
)
from apps.reports.financial import DATE_RANGE_CHOICES, export_form_payload
from apps.reports.financial_views import (
    body_data,
    export_filename,
    get_organization_id,
    merge_export_options,
    pdf_response,
    request_filters,
    resolve_organization,
)


class ExpenseReportIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Expenses",
                "reports": list(EXPENSE_REPORTS),
            }
        )


class ExpenseReportOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Expenses",
                "reports": list(EXPENSE_REPORTS),
                "date_range": list(DATE_RANGE_CHOICES),
                "default_date_range": "this_month",
            }
        )


class ExpensesByCategoryFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=expenses_by_category_form_payload())


class ExpensesByCategoryOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = expenses_by_category_form_payload()
        data["export_form"] = export_form_payload(
            "expenses_by_category",
            title="Expenses by Category",
        )
        return api_success(data=data)


class ExpensesByCategoryExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload(
                "expenses_by_category",
                title="Expenses by Category",
            )
        )


class ExpensesByCategoryView(APIView):
    permission_classes = [IsAuthenticated]

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
        data = build_expenses_by_category_report(organization, request_filters(request))
        return api_success(data=data)


class ExpensesByCategoryExportView(APIView):
    permission_classes = [IsAuthenticated]

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
        report = build_expenses_by_category_report(organization, request_filters(request))
        export_format = (
            request.query_params.get("export_format")
            or body_data(request).get("export_format")
            or "pdf"
        ).strip().lower()
        filename = export_filename(report, export_options)
        if export_format == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["Category", "Amount"])
            if report.get("empty"):
                writer.writerow([report.get("empty_message") or "", ""])
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get("category_display") or row.get("category") or "",
                            row.get("amount_display") or row.get("amount") or "",
                        ]
                    )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
            return response
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
