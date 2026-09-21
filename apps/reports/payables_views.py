import csv
import io

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
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
from apps.reports.payables import (
    PAYABLE_REPORTS,
    build_payments_made_report,
    build_vendor_balance_summary_report,
    payments_made_form_payload,
    vendor_balance_summary_form_payload,
)


class PayableReportIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Payables",
                "reports": list(PAYABLE_REPORTS),
            }
        )


class PayableReportOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Payables",
                "reports": list(PAYABLE_REPORTS),
                "date_range": list(DATE_RANGE_CHOICES),
                "default_date_range": "this_month",
            }
        )


class PaymentsMadeFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=payments_made_form_payload())


class PaymentsMadeOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = payments_made_form_payload()
        data["export_form"] = export_form_payload(
            "payments_made",
            title="Payments Made",
        )
        return api_success(data=data)


class PaymentsMadeExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload("payments_made", title="Payments Made")
        )


class PaymentsMadeView(APIView):
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
        data = build_payments_made_report(organization, request_filters(request))
        return api_success(data=data)


class PaymentsMadeExportView(APIView):
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
        report = build_payments_made_report(organization, request_filters(request))
        export_format = (
            request.query_params.get("export_format")
            or body_data(request).get("export_format")
            or "pdf"
        ).strip().lower()
        filename = export_filename(report, export_options)
        if export_format == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["Payment Number", "Date", "Vendor", "Amount"])
            if report.get("empty"):
                writer.writerow([report.get("empty_message") or "", "", "", ""])
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get("payment_number") or "",
                            row.get("date_display") or row.get("date") or "",
                            row.get("vendor_display") or row.get("vendor") or "",
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


class VendorBalanceSummaryFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=vendor_balance_summary_form_payload())


class VendorBalanceSummaryOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = vendor_balance_summary_form_payload()
        data["export_form"] = export_form_payload(
            "vendor_balance_summary",
            title="Vendor Balance Summary",
        )
        return api_success(data=data)


class VendorBalanceSummaryExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload(
                "vendor_balance_summary",
                title="Vendor Balance Summary",
            )
        )


class VendorBalanceSummaryView(APIView):
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
        data = build_vendor_balance_summary_report(
            organization,
            request_filters(request),
        )
        return api_success(data=data)


class VendorBalanceSummaryExportView(APIView):
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
        report = build_vendor_balance_summary_report(
            organization,
            request_filters(request),
        )
        export_format = (
            request.query_params.get("export_format")
            or body_data(request).get("export_format")
            or "pdf"
        ).strip().lower()
        filename = export_filename(report, export_options)
        if export_format == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(
                ["Vendor Name", "Billed Amount", "Amount Paid", "Closing Balance"]
            )
            if report.get("empty"):
                writer.writerow([report.get("empty_message") or "", "", "", ""])
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get("vendor_name") or "",
                            row.get("billed_amount_display") or row.get("billed_amount") or "",
                            row.get("amount_paid_display") or row.get("amount_paid") or "",
                            row.get("closing_balance_display") or row.get("closing_balance") or "",
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
