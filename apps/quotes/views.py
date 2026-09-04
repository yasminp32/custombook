from uuid import UUID

from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.quotes.filters import QUOTE_STATUS_FILTERS, QUOTE_TAB_FILTERS, QuoteFilter
from apps.quotes.models import Quote
from apps.quotes.serializers import QuoteSerializer, QuoteWriteSerializer

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "last_modified_time": "updated_at",
    "updated_at": "updated_at",
    "date": "quote_date",
    "quote_date": "quote_date",
    "quote_number": "quote_number",
    "customer_name": "customer__display_name",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_quote_queryset(user):
    return Quote.objects.filter(organization__owner=user).select_related(
        "organization",
        "customer",
        "created_by",
    ).prefetch_related("lines__item")


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


def get_quote_id_param(request):
    quote_id = request.query_params.get("quote_id") or request.query_params.get("id")
    if not quote_id:
        return None, api_error(
            "quote_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(quote_id, "quote_id")


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


def filtered_quote_queryset(request):
    queryset = get_quote_queryset(request.user)
    quote_filter = QuoteFilter(request.query_params, queryset=queryset)
    if not quote_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=quote_filter.errors)
    queryset, error_response = apply_sorting(quote_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


class QuoteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        quote_id = request.query_params.get("quote_id") or request.query_params.get("id")
        if quote_id:
            parsed_id, error_response = parse_uuid(quote_id, "quote_id")
            if error_response:
                return error_response
            quote = get_quote_queryset(request.user).filter(pk=parsed_id).first()
            if not quote:
                return api_error("Quote not found.", status_code=status.HTTP_404_NOT_FOUND)
            return api_success(data=QuoteSerializer(quote).data)

        queryset, error_response = filtered_quote_queryset(request)
        if error_response:
            return error_response

        response = paginate_queryset(request, queryset, serializer=QuoteSerializer)
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
                "Organization not found. Complete organization setup before creating quotes.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = QuoteWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            quote = serializer.save(organization=organization, created_by=request.user)
        except IntegrityError:
            return api_error(
                "Quote number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        quote = get_quote_queryset(request.user).get(pk=quote.pk)
        message = (
            "Quote sent successfully."
            if quote.status == Quote.Status.SENT
            else "Quote saved as draft."
        )
        return api_success(
            data=QuoteSerializer(quote).data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        quote_id, error_response = get_quote_id_param(request)
        if error_response:
            return error_response
        quote = get_quote_queryset(request.user).filter(pk=quote_id).first()
        if not quote:
            return api_error("Quote not found.", status_code=status.HTTP_404_NOT_FOUND)

        serializer = QuoteWriteSerializer(quote, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            quote = serializer.save()
        except IntegrityError:
            return api_error(
                "Quote number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        quote = get_quote_queryset(request.user).get(pk=quote.pk)
        return api_success(
            data=QuoteSerializer(quote).data,
            message="Quote updated successfully.",
        )

    def patch(self, request):
        quote_id, error_response = get_quote_id_param(request)
        if error_response:
            return error_response
        quote = get_quote_queryset(request.user).filter(pk=quote_id).first()
        if not quote:
            return api_error("Quote not found.", status_code=status.HTTP_404_NOT_FOUND)

        serializer = QuoteWriteSerializer(quote, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            quote = serializer.save()
        except IntegrityError:
            return api_error(
                "Quote number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        quote = get_quote_queryset(request.user).get(pk=quote.pk)
        return api_success(
            data=QuoteSerializer(quote).data,
            message="Quote updated successfully.",
        )

    def delete(self, request):
        quote_id, error_response = get_quote_id_param(request)
        if error_response:
            return error_response
        quote = get_quote_queryset(request.user).filter(pk=quote_id).first()
        if not quote:
            return api_error("Quote not found.", status_code=status.HTTP_404_NOT_FOUND)
        quote.delete()
        return api_success(message="Quote deleted successfully.")


class QuoteOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_quote_queryset(request.user)
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in QUOTE_TAB_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in QUOTE_STATUS_FILTERS
                ],
                "tax_types": [
                    {"key": key, "label": label} for key, label in Quote.TaxType.choices
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "last_modified_time", "label": "Last Modified Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "quote_number", "label": "Quote Number"},
                    {"key": "customer_name", "label": "Customer Name"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "counts": {
                    "all": queryset.count(),
                    "draft": queryset.filter(status=Quote.Status.DRAFT).count(),
                    "sent": queryset.filter(status=Quote.Status.SENT).count(),
                },
                "actions": [
                    {
                        "key": "save_as_draft",
                        "label": "Save as Draft",
                        "path": "/api/quotes/",
                    },
                    {
                        "key": "save_and_send",
                        "label": "Save and Send",
                        "path": "/api/quotes/",
                    },
                    {
                        "key": "refresh",
                        "label": "Refresh",
                        "path": "/api/quotes/refresh/",
                    },
                    {
                        "key": "export",
                        "label": "Export Quotes",
                        "path": "/api/quotes/export/",
                    },
                ],
            }
        )


class QuoteRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_quote_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=QuoteSerializer)
        if response is not None:
            response.data["message"] = "Quotes refreshed."
            return response
        return api_success(data=[], message="Quotes refreshed.")


class QuoteExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_quote_queryset(request)
        if error_response:
            return error_response
        rows = QuoteSerializer(queryset, many=True).data
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
                    "quote_id",
                    "quote_number",
                    "customer_name",
                    "quote_date",
                    "status",
                    "total_amount",
                    "currency",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "quote_id": row["quote_id"],
                        "quote_number": row["quote_number"],
                        "customer_name": row["customer_name"],
                        "quote_date": row["quote_date"],
                        "status": row["status"],
                        "total_amount": row["total_amount"],
                        "currency": row["currency"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="quotes.csv"'
            return response
        return api_success(
            data={"count": len(rows), "quotes": rows},
            message="Quotes exported successfully.",
        )


class QuoteSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quote_id, error_response = get_quote_id_param(request)
        if error_response:
            return error_response
        quote = get_quote_queryset(request.user).filter(pk=quote_id).first()
        if not quote:
            return api_error("Quote not found.", status_code=status.HTTP_404_NOT_FOUND)
        if not quote.lines.exists():
            return api_error(
                "Add at least one line item before sending a quote.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        quote.status = Quote.Status.SENT
        if not quote.sent_at:
            quote.sent_at = timezone.now()
        quote.save(update_fields=["status", "sent_at", "updated_at"])
        quote = get_quote_queryset(request.user).get(pk=quote.pk)
        return api_success(
            data=QuoteSerializer(quote).data,
            message="Quote sent successfully.",
        )
