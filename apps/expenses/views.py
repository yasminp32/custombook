from datetime import date
from uuid import UUID

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.serializers import ValidationError as SerializerValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.expenses.filters import (
    EXPENSE_STATUS_FILTERS,
    EXPENSE_TAB_FILTERS,
    ExpenseFilter,
)
from apps.expenses.models import Expense
from apps.expenses.serializers import (
    ExpenseCategorySerializer,
    ExpenseSerializer,
    ExpenseWriteSerializer,
    ensure_default_categories,
)
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.vendors.models import Vendor

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "date": "expense_date",
    "expense_date": "expense_date",
    "category": "category__name",
    "category_name": "category__name",
    "amount": "amount",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_expense_queryset(user):
    return Expense.objects.filter(organization__owner=user).select_related(
        "organization",
        "category",
        "vendor",
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


def get_expense_id_param(request):
    expense_id = (
        request.query_params.get("expense_id")
        or request.query_params.get("id")
        or request.data.get("expense_id")
        or request.data.get("id")
    )
    if not expense_id:
        return None, api_error(
            "expense_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(expense_id, "expense_id")


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


def filtered_expense_queryset(request):
    queryset = get_expense_queryset(request.user)
    expense_filter = ExpenseFilter(request.query_params, queryset=queryset)
    if not expense_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=expense_filter.errors)
    queryset, error_response = apply_sorting(expense_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def expense_counts(queryset):
    return {
        "all": queryset.count(),
        "unbilled": queryset.filter(status=Expense.Status.UNBILLED).count(),
        "billed": queryset.filter(status=Expense.Status.BILLED).count(),
        "reimbursed": queryset.filter(status=Expense.Status.REIMBURSED).count(),
        "non_billable": queryset.filter(status=Expense.Status.NON_BILLABLE).count(),
    }


def vendor_option(vendor):
    name = vendor.display_name or vendor.company_name or ""
    return {
        "vendor_id": vendor.id,
        "display_name": name,
        "company_name": vendor.company_name or "",
    }


def success_message(expense):
    if expense.status == Expense.Status.BILLED:
        return "Expense saved as billed."
    return "Expense saved successfully."


def build_expense_form(user, organization):
    queryset = get_expense_queryset(user)
    categories = ensure_default_categories(organization).order_by("name")
    vendors = Vendor.objects.filter(
        organization=organization,
        status=Vendor.Status.ACTIVE,
    ).order_by("display_name", "company_name")[:100]
    today = date.today()
    currency = (organization.currency if organization else "INR") or "INR"
    return {
        "title": "New Expense",
        "defaults": {
            "expense_date": today.isoformat(),
            "expense_date_label": today.strftime("%d %b %Y"),
            "reference_number": "",
            "amount": "0.00",
            "currency": currency,
            "status": Expense.Status.UNBILLED,
            "action": "save",
        },
        "fields": {
            "category_id": {
                "label": "Category",
                "required": True,
                "placeholder": "Select a category",
            },
            "vendor_id": {
                "label": "Vendor",
                "required": False,
                "placeholder": "Select a vendor",
            },
            "expense_date": {
                "label": "Expense Date",
                "required": True,
            },
            "reference_number": {
                "label": "Reference#",
                "required": False,
            },
            "amount": {
                "label": "Amount",
                "required": True,
            },
        },
        "categories": ExpenseCategorySerializer(categories, many=True).data,
        "vendors": [vendor_option(row) for row in vendors],
        "counts": expense_counts(queryset),
        "actions": [
            {"key": "save", "label": "Save", "path": "/api/expenses/"},
            {
                "key": "save_as_billed",
                "label": "Save as Billed",
                "path": "/api/expenses/",
            },
        ],
        "create_path": "/api/expenses/",
        "export_path": "/api/expenses/export/",
        "refresh_path": "/api/expenses/refresh/",
    }


class ExpenseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        expense_id = request.query_params.get("expense_id") or request.query_params.get("id")
        if expense_id:
            parsed_id, error_response = parse_uuid(expense_id, "expense_id")
            if error_response:
                return error_response
            expense = get_expense_queryset(request.user).filter(pk=parsed_id).first()
            if not expense:
                return api_error("Expense not found.", status_code=status.HTTP_404_NOT_FOUND)
            return api_success(data=ExpenseSerializer(expense).data)

        queryset, error_response = filtered_expense_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=ExpenseSerializer)
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
                "Organization not found. Complete organization setup before creating expenses.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        ensure_default_categories(organization)
        serializer = ExpenseWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            expense = serializer.save(organization=organization, created_by=request.user)
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        expense = get_expense_queryset(request.user).get(pk=expense.pk)
        return api_success(
            data=ExpenseSerializer(expense).data,
            message=success_message(expense),
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        expense_id, error_response = get_expense_id_param(request)
        if error_response:
            return error_response
        expense = get_expense_queryset(request.user).filter(pk=expense_id).first()
        if not expense:
            return api_error("Expense not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = ExpenseWriteSerializer(expense, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        try:
            expense = serializer.save()
        except SerializerValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        expense = get_expense_queryset(request.user).get(pk=expense.pk)
        return api_success(
            data=ExpenseSerializer(expense).data,
            message="Expense updated successfully.",
        )

    def delete(self, request):
        expense_id, error_response = get_expense_id_param(request)
        if error_response:
            return error_response
        expense = get_expense_queryset(request.user).filter(pk=expense_id).first()
        if not expense:
            return api_error("Expense not found.", status_code=status.HTTP_404_NOT_FOUND)
        expense.delete()
        return api_success(message="Expense deleted successfully.")


class ExpenseOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_expense_queryset(request.user)
        organization = resolve_organization(
            request.user,
            request.query_params.get("organization_id"),
        )
        categories = []
        if organization:
            categories = ExpenseCategorySerializer(
                ensure_default_categories(organization).order_by("name"),
                many=True,
            ).data
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in EXPENSE_TAB_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in EXPENSE_STATUS_FILTERS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "date", "label": "Date"},
                    {"key": "category", "label": "Category"},
                    {"key": "amount", "label": "Amount"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/expenses/form/",
                "categories": categories,
                "counts": expense_counts(queryset),
                "actions": [
                    {"key": "save", "label": "Save", "path": "/api/expenses/"},
                    {
                        "key": "save_as_billed",
                        "label": "Save as Billed",
                        "path": "/api/expenses/",
                    },
                    {"key": "export", "label": "Export Expenses", "path": "/api/expenses/export/"},
                    {"key": "refresh", "label": "Refresh", "path": "/api/expenses/refresh/"},
                ],
            }
        )


class ExpenseFormView(APIView):
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
        data = build_expense_form(request.user, organization)
        expense_id = request.query_params.get("expense_id") or request.query_params.get("id")
        if expense_id:
            parsed_id, error_response = parse_uuid(expense_id, "expense_id")
            if error_response:
                return error_response
            expense = get_expense_queryset(request.user).filter(pk=parsed_id).first()
            if not expense:
                return api_error("Expense not found.", status_code=status.HTTP_404_NOT_FOUND)
            data["title"] = "Edit Expense"
            data["expense"] = ExpenseSerializer(expense).data
        return api_success(data=data)


class ExpenseRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_expense_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=ExpenseSerializer)
        if response is not None:
            response.data["message"] = "Expenses refreshed."
            return response
        return api_success(data=[], message="Expenses refreshed.")


class ExpenseExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_expense_queryset(request)
        if error_response:
            return error_response
        rows = ExpenseSerializer(queryset, many=True).data
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
                    "expense_id",
                    "category_name",
                    "vendor_name",
                    "expense_date",
                    "reference_number",
                    "amount",
                    "currency",
                    "status",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "expense_id": row["expense_id"],
                        "category_name": row["category_name"],
                        "vendor_name": row["vendor_name"],
                        "expense_date": row["expense_date"],
                        "reference_number": row["reference_number"],
                        "amount": row["amount"],
                        "currency": row["currency"],
                        "status": row["status"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="expenses.csv"'
            return response
        return api_success(
            data={"count": len(rows), "expenses": rows},
            message="Expenses exported successfully.",
        )
