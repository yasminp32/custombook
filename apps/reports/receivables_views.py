import csv
import io

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.reports.financial import AS_OF_DATE_CHOICES, DATE_RANGE_CHOICES, export_form_payload
from apps.reports.financial_views import (
    body_data,
    export_filename,
    get_organization_id,
    merge_export_options,
    pdf_response,
    request_filters,
    resolve_organization,
)
from apps.reports.receivables import (
    AGING_BUCKETS,
    RECEIVABLE_REPORTS,
    ar_aging_details_form_payload,
    ar_aging_summary_form_payload,
    build_ar_aging_details_report,
    build_ar_aging_summary_report,
    build_customer_balance_summary_report,
    build_payments_received_report,
    customer_balance_summary_form_payload,
    payments_received_form_payload,
)


class ReceivableReportIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Receivables",
                "reports": list(RECEIVABLE_REPORTS),
            }
        )


class ReceivableReportOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Receivables",
                "reports": list(RECEIVABLE_REPORTS),
                "date_range": list(DATE_RANGE_CHOICES),
                "default_date_range": "this_month",
                "as_of_date": list(AS_OF_DATE_CHOICES),
                "default_as_of_date": "today",
            }
        )


class CustomerBalanceSummaryFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=customer_balance_summary_form_payload())


class CustomerBalanceSummaryOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = customer_balance_summary_form_payload()
        data["export_form"] = export_form_payload(
            "customer_balance_summary",
            title="Customer Balance Summary",
        )
        return api_success(data=data)


class CustomerBalanceSummaryExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload(
                "customer_balance_summary",
                title="Customer Balance Summary",
            )
        )


class CustomerBalanceSummaryView(APIView):
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
        data = build_customer_balance_summary_report(
            organization,
            request_filters(request),
        )
        return api_success(data=data)


class CustomerBalanceSummaryExportView(APIView):
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
        report = build_customer_balance_summary_report(
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
                [
                    "Customer Name",
                    "Invoiced Amount",
                    "Amount Received",
                    "Closing Balance",
                ]
            )
            if report.get("empty"):
                writer.writerow([report.get("empty_message") or "", "", "", ""])
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get("customer_name"),
                            row.get("invoiced_amount_display") or row.get("invoiced_amount"),
                            row.get("amount_received_display") or row.get("amount_received"),
                            row.get("closing_balance_display") or row.get("closing_balance"),
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


class ARAgingSummaryFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=ar_aging_summary_form_payload())


class ARAgingSummaryOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = ar_aging_summary_form_payload()
        data["export_form"] = export_form_payload(
            "ar_aging_summary",
            title="AR Aging Summary",
        )
        return api_success(data=data)


class ARAgingSummaryExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload("ar_aging_summary", title="AR Aging Summary")
        )


class ARAgingSummaryView(APIView):
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
        data = build_ar_aging_summary_report(organization, request_filters(request))
        return api_success(data=data)


class ARAgingSummaryExportView(APIView):
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
        report = build_ar_aging_summary_report(organization, request_filters(request))
        export_format = (
            request.query_params.get("export_format")
            or body_data(request).get("export_format")
            or "pdf"
        ).strip().lower()
        filename = export_filename(report, export_options)
        if export_format == "csv":
            headers = ["Customer Name"] + [label for _key, label in AGING_BUCKETS] + ["Total"]
            keys = ["customer_name"] + [key for key, _label in AGING_BUCKETS] + ["total"]
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(headers)
            if report.get("empty"):
                writer.writerow([report.get("empty_message") or ""] + [""] * (len(keys) - 1))
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get(f"{key}_display") or row.get(key) or ""
                            for key in keys
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


class ARAgingDetailsFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=ar_aging_details_form_payload())


class ARAgingDetailsOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = ar_aging_details_form_payload()
        data["export_form"] = export_form_payload(
            "ar_aging_details",
            title="AR Aging Details",
        )
        return api_success(data=data)


class ARAgingDetailsExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload("ar_aging_details", title="AR Aging Details")
        )


class ARAgingDetailsView(APIView):
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
        data = build_ar_aging_details_report(organization, request_filters(request))
        return api_success(data=data)


class ARAgingDetailsExportView(APIView):
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
        report = build_ar_aging_details_report(organization, request_filters(request))
        export_format = (
            request.query_params.get("export_format")
            or body_data(request).get("export_format")
            or "pdf"
        ).strip().lower()
        filename = export_filename(report, export_options)
        if export_format == "csv":
            headers = [
                "Date",
                "Due Date",
                "Transaction#",
                "Type",
                "Status",
                "Customer Name",
                "Age",
                "Amount",
            ]
            keys = [
                "date",
                "due_date",
                "transaction_number",
                "type",
                "status",
                "customer_name",
                "age",
                "amount",
            ]
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(headers)
            if report.get("empty"):
                writer.writerow([report.get("empty_message") or ""] + [""] * 7)
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get(f"{key}_display") or row.get(key) or ""
                            for key in keys
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


class PaymentsReceivedFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=payments_received_form_payload())


class PaymentsReceivedOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = payments_received_form_payload()
        data["export_form"] = export_form_payload(
            "payments_received",
            title="Payments Received",
        )
        return api_success(data=data)


class PaymentsReceivedExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload("payments_received", title="Payments Received")
        )


class PaymentsReceivedView(APIView):
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
        data = build_payments_received_report(organization, request_filters(request))
        return api_success(data=data)


class PaymentsReceivedExportView(APIView):
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
        report = build_payments_received_report(organization, request_filters(request))
        export_format = (
            request.query_params.get("export_format")
            or body_data(request).get("export_format")
            or "pdf"
        ).strip().lower()
        filename = export_filename(report, export_options)
        if export_format == "csv":
            headers = [
                "Payment Number",
                "Date",
                "Status",
                "Reference Number",
                "Customer Name",
                "Payment Mode",
                "Amount",
                "Unused Amount",
            ]
            keys = [
                "payment_number",
                "date",
                "status",
                "reference_number",
                "customer_name",
                "payment_mode",
                "amount",
                "unused_amount",
            ]
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(headers)
            if report.get("empty"):
                writer.writerow([report.get("empty_message") or ""] + [""] * 7)
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get(f"{key}_display") or row.get(key) or ""
                            for key in keys
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
