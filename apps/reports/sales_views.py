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
from apps.reports.sales import (
    SALES_REPORTS,
    build_sales_by_customer_report,
    build_sales_by_item_report,
    build_sales_by_sales_person_report,
    sales_by_customer_form_payload,
    sales_by_item_form_payload,
    sales_by_sales_person_form_payload,
)


class SalesReportIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Sales",
                "reports": list(SALES_REPORTS),
            }
        )


class SalesReportOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "title": "Sales",
                "reports": list(SALES_REPORTS),
                "date_range": list(DATE_RANGE_CHOICES),
                "default_date_range": "this_month",
            }
        )


class SalesByCustomerFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=sales_by_customer_form_payload())


class SalesByCustomerOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = sales_by_customer_form_payload()
        data["export_form"] = export_form_payload(
            "sales_by_customer",
            title="Sales by Customer",
        )
        return api_success(data=data)


class SalesByCustomerExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload("sales_by_customer", title="Sales by Customer")
        )


class SalesByCustomerView(APIView):
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
        data = build_sales_by_customer_report(organization, request_filters(request))
        return api_success(data=data)


class SalesByCustomerExportView(APIView):
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
        report = build_sales_by_customer_report(organization, request_filters(request))
        export_format = (
            request.query_params.get("export_format")
            or body_data(request).get("export_format")
            or "pdf"
        ).strip().lower()
        filename = export_filename(report, export_options)
        if export_format == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["Name", "Invoice Count", "Sales", "Sales With Tax"])
            if report.get("empty"):
                writer.writerow([report.get("empty_message") or "", "", "", ""])
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get("name"),
                            row.get("invoice_count"),
                            row.get("sales_display") or row.get("sales"),
                            row.get("sales_with_tax_display") or row.get("sales_with_tax"),
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


class SalesByItemFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=sales_by_item_form_payload())


class SalesByItemOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = sales_by_item_form_payload()
        data["export_form"] = export_form_payload(
            "sales_by_item",
            title="Sales by Item",
        )
        return api_success(data=data)


class SalesByItemExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload("sales_by_item", title="Sales by Item")
        )


class SalesByItemView(APIView):
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
        data = build_sales_by_item_report(organization, request_filters(request))
        return api_success(data=data)


class SalesByItemExportView(APIView):
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
        report = build_sales_by_item_report(organization, request_filters(request))
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
                ["Item Name", "SKU", "Quantity Sold", "Amount", "Average Price"]
            )
            if report.get("empty"):
                writer.writerow([report.get("empty_message") or "", "", "", "", ""])
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get("item_name"),
                            row.get("sku"),
                            row.get("quantity_sold"),
                            row.get("amount_display") or row.get("amount"),
                            row.get("average_price_display") or row.get("average_price"),
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


class SalesBySalesPersonFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=sales_by_sales_person_form_payload())


class SalesBySalesPersonOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = sales_by_sales_person_form_payload()
        data["export_form"] = export_form_payload(
            "sales_by_sales_person",
            title="Sales by Sales Person",
        )
        return api_success(data=data)


class SalesBySalesPersonExportFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data=export_form_payload(
                "sales_by_sales_person",
                title="Sales by Sales Person",
            )
        )


class SalesBySalesPersonView(APIView):
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
        data = build_sales_by_sales_person_report(organization, request_filters(request))
        return api_success(data=data)


class SalesBySalesPersonExportView(APIView):
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
        report = build_sales_by_sales_person_report(
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
                    "Name",
                    "Invoice Count",
                    "Invoice Sales",
                    "Invoice Sales With Tax",
                    "Credit Note Count",
                    "Credit Note Sales",
                ]
            )
            if report.get("empty"):
                writer.writerow(
                    [report.get("empty_message") or "", "", "", "", "", ""]
                )
            else:
                for row in report.get("rows") or []:
                    writer.writerow(
                        [
                            row.get("name"),
                            row.get("invoice_count"),
                            row.get("invoice_sales_display") or row.get("invoice_sales"),
                            row.get("invoice_sales_with_tax_display")
                            or row.get("invoice_sales_with_tax"),
                            row.get("credit_note_count"),
                            row.get("credit_note_sales_display")
                            or row.get("credit_note_sales"),
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
