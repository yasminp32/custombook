import csv
from io import StringIO, TextIOWrapper
from uuid import UUID

from django.db.models import DecimalField, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.vendors.filters import (
    VENDOR_STATUS_FILTERS,
    VENDOR_TAB_FILTERS,
    VendorFilter,
)
from apps.vendors.models import Vendor, VendorPayment
from apps.vendors.payment_filters import VendorPaymentFilter
from apps.vendors.serializers import (
    VendorPaymentSerializer,
    VendorPaymentWriteSerializer,
    VendorSerializer,
    VendorWriteSerializer,
)

SORT_FIELDS = {
    "created_time": "created_at",
    "created_at": "created_at",
    "name": "display_name",
    "display_name": "display_name",
    "company_name": "company_name",
    "payables": "payables_sort",
    "opening_balance": "payables_sort",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_vendor_queryset(user):
    return (
        Vendor.objects.filter(organization__owner=user)
        .select_related("organization", "payment_term", "created_by")
        .annotate(
            payables_sort=Coalesce(
                "opening_balance",
                Value(0),
                output_field=DecimalField(max_digits=19, decimal_places=4),
            )
        )
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


def get_vendor_id_param(request):
    vendor_id = (
        request.query_params.get("vendor_id")
        or request.query_params.get("id")
        or request.data.get("vendor_id")
        or request.data.get("id")
    )
    if not vendor_id:
        return None, api_error(
            "vendor_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(vendor_id, "vendor_id")


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


def filtered_vendor_queryset(request):
    queryset = get_vendor_queryset(request.user)
    vendor_filter = VendorFilter(request.query_params, queryset=queryset)
    if not vendor_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=vendor_filter.errors)
    queryset, error_response = apply_sorting(vendor_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


def vendor_counts(queryset):
    return {
        "all": queryset.count(),
        "active": queryset.filter(status=Vendor.Status.ACTIVE).count(),
        "inactive": queryset.filter(status=Vendor.Status.INACTIVE).count(),
    }


def build_vendor_form(user, organization):
    queryset = get_vendor_queryset(user)
    return {
        "title": "New Vendor",
        "defaults": {
            "display_name": "",
            "company_name": "",
            "email": "",
            "phone": "",
            "opening_balance": "0.00",
            "payables": "0.00",
            "status": Vendor.Status.ACTIVE,
        },
        "fields": {
            "display_name": {
                "label": "Display Name",
                "required": True,
                "placeholder": "Enter display name",
            },
            "company_name": {
                "label": "Company Name",
                "required": False,
                "placeholder": "Enter company name",
            },
            "email": {
                "label": "Email",
                "required": False,
                "placeholder": "name@example.com",
            },
            "phone": {
                "label": "Phone",
                "required": False,
                "placeholder": "+971 50 123 4567",
            },
            "opening_balance": {
                "label": "Opening Balance (Payables)",
                "required": False,
            },
        },
        "counts": vendor_counts(queryset),
        "actions": [
            {"key": "save", "label": "Save", "path": "/api/vendors/"},
        ],
        "create_path": "/api/vendors/",
        "import_path": "/api/vendors/import/",
        "export_path": "/api/vendors/export/",
    }


class VendorView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor_id = request.query_params.get("vendor_id") or request.query_params.get("id")
        if vendor_id:
            parsed_id, error_response = parse_uuid(vendor_id, "vendor_id")
            if error_response:
                return error_response
            vendor = get_vendor_queryset(request.user).filter(pk=parsed_id).first()
            if not vendor:
                return api_error("Vendor not found.", status_code=status.HTTP_404_NOT_FOUND)
            return api_success(data=VendorSerializer(vendor).data)

        queryset, error_response = filtered_vendor_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=VendorSerializer)
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
                "Organization not found. Complete organization setup before creating vendors.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = VendorWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        created_by = serializer.validate_created_by_reference(request.user)
        vendor = serializer.save(organization=organization, created_by=created_by)
        vendor = get_vendor_queryset(request.user).get(pk=vendor.pk)
        return api_success(
            data=VendorSerializer(vendor).data,
            message="Vendor created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        vendor_id, error_response = get_vendor_id_param(request)
        if error_response:
            return error_response
        vendor = get_vendor_queryset(request.user).filter(pk=vendor_id).first()
        if not vendor:
            return api_error("Vendor not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = VendorWriteSerializer(vendor, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        vendor = serializer.save()
        vendor = get_vendor_queryset(request.user).get(pk=vendor.pk)
        return api_success(
            data=VendorSerializer(vendor).data,
            message="Vendor updated successfully.",
        )

    def delete(self, request):
        vendor_id, error_response = get_vendor_id_param(request)
        if error_response:
            return error_response
        vendor = get_vendor_queryset(request.user).filter(pk=vendor_id).first()
        if not vendor:
            return api_error("Vendor not found.", status_code=status.HTTP_404_NOT_FOUND)
        vendor.delete()
        return api_success(message="Vendor deleted successfully.")


class VendorOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_vendor_queryset(request.user)
        return api_success(
            data={
                "tabs": [{"key": key, "label": label} for key, label in VENDOR_TAB_FILTERS],
                "statuses": [
                    {"key": key, "label": label} for key, label in VENDOR_STATUS_FILTERS
                ],
                "sort_fields": [
                    {"key": "created_time", "label": "Created Time"},
                    {"key": "name", "label": "Name"},
                    {"key": "company_name", "label": "Company Name"},
                    {"key": "payables", "label": "Payables"},
                ],
                "default_sort": {"sort_by": "created_time", "sort_order": "desc"},
                "form_path": "/api/vendors/form/",
                "counts": vendor_counts(queryset),
                "actions": [
                    {"key": "save", "label": "Save", "path": "/api/vendors/"},
                    {"key": "import", "label": "Import Vendors", "path": "/api/vendors/import/"},
                    {"key": "export", "label": "Export Vendors", "path": "/api/vendors/export/"},
                    {"key": "refresh", "label": "Refresh", "path": "/api/vendors/refresh/"},
                ],
            }
        )


class VendorFormView(APIView):
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
        data = build_vendor_form(request.user, organization)
        vendor_id = request.query_params.get("vendor_id") or request.query_params.get("id")
        if vendor_id:
            parsed_id, error_response = parse_uuid(vendor_id, "vendor_id")
            if error_response:
                return error_response
            vendor = get_vendor_queryset(request.user).filter(pk=parsed_id).first()
            if not vendor:
                return api_error("Vendor not found.", status_code=status.HTTP_404_NOT_FOUND)
            data["title"] = "Edit Vendor"
            data["vendor"] = VendorSerializer(vendor).data
        return api_success(data=data)


class VendorRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_vendor_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(request, queryset, serializer=VendorSerializer)
        if response is not None:
            response.data["message"] = "Vendors refreshed."
            return response
        return api_success(data=[], message="Vendors refreshed.")


class VendorExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_vendor_queryset(request)
        if error_response:
            return error_response
        rows = VendorSerializer(queryset, many=True).data
        export_format = (
            request.query_params.get("export_format")
            or request.query_params.get("format")
            or "json"
        ).strip().lower()
        if export_format == "csv":
            buffer = StringIO()
            writer = csv.DictWriter(
                buffer,
                fieldnames=[
                    "vendor_id",
                    "display_name",
                    "company_name",
                    "email",
                    "phone",
                    "payables",
                    "status",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "vendor_id": row["vendor_id"],
                        "display_name": row["display_name"],
                        "company_name": row["company_name"],
                        "email": row["email"],
                        "phone": row["phone"],
                        "payables": row["payables"],
                        "status": row["status"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="vendors.csv"'
            return response
        return api_success(
            data={"count": len(rows), "vendors": rows},
            message="Vendors exported successfully.",
        )


class VendorImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

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
        rows = request.data.get("vendors")
        if rows is None:
            upload = request.FILES.get("file")
            if not upload:
                return api_error(
                    "Upload a CSV file as `file` or send a `vendors` JSON array.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            try:
                text = TextIOWrapper(upload.file, encoding="utf-8")
                reader = csv.DictReader(text)
                rows = list(reader)
            except Exception:
                return api_error(
                    "Unable to read CSV file. Use headers: display_name,company_name,email,phone,opening_balance,status",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        if not isinstance(rows, list) or not rows:
            return api_error(
                "No vendor rows found to import.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        created = []
        errors = []
        for index, row in enumerate(rows):
            payload = {
                "display_name": row.get("display_name") or row.get("name") or "",
                "company_name": row.get("company_name") or "",
                "email": row.get("email") or "",
                "phone": row.get("phone") or "",
                "opening_balance": row.get("opening_balance") or row.get("payables") or "0.00",
                "status": row.get("status") or Vendor.Status.ACTIVE,
            }
            serializer = VendorWriteSerializer(data=payload)
            if not serializer.is_valid():
                errors.append({"row": index + 1, "errors": serializer.errors})
                continue
            created_by = serializer.validate_created_by_reference(request.user)
            vendor = serializer.save(organization=organization, created_by=created_by)
            created.append(VendorSerializer(get_vendor_queryset(request.user).get(pk=vendor.pk)).data)
        if not created:
            return api_error(
                "No vendors were imported.",
                errors={"rows": errors},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return api_success(
            data={"imported": len(created), "failed": len(errors), "vendors": created, "errors": errors},
            message=f"{len(created)} vendor(s) imported.",
            status_code=status.HTTP_201_CREATED,
        )


def get_vendor_payment_queryset(user):
    return VendorPayment.objects.filter(
        organization__owner=user,
    ).select_related("organization", "vendor")


def get_vendor_payment_id_param(request):
    vendor_payment_id = (
        request.query_params.get("vendor_payment_id")
        or request.query_params.get("id")
    )
    if not vendor_payment_id:
        return None, api_error(
            "vendor_payment_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return vendor_payment_id, None


class VendorPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor_payment_id = (
            request.query_params.get("vendor_payment_id")
            or request.query_params.get("id")
        )
        if vendor_payment_id:
            payment = get_object_or_404(
                get_vendor_payment_queryset(request.user),
                pk=vendor_payment_id,
            )
            return api_success(data=VendorPaymentSerializer(payment).data)

        queryset = get_vendor_payment_queryset(request.user)
        payment_filter = VendorPaymentFilter(request.query_params, queryset=queryset)
        if not payment_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=payment_filter.errors)

        response = paginate_queryset(
            request,
            payment_filter.qs.order_by("-created_at"),
            serializer=VendorPaymentSerializer,
        )
        if response is not None:
            return response
        return api_success(data=[])

    def post(self, request):
        vendor_id = request.data.get("vendor_id")
        if not vendor_id:
            return api_error("vendor_id is required.", status_code=status.HTTP_400_BAD_REQUEST)
        get_object_or_404(get_vendor_queryset(request.user), pk=vendor_id)
        serializer = VendorPaymentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        payment = serializer.save()
        return api_success(
            data=VendorPaymentSerializer(payment).data,
            message="Vendor payment created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        vendor_payment_id, error_response = get_vendor_payment_id_param(request)
        if error_response:
            return error_response
        payment = get_object_or_404(
            get_vendor_payment_queryset(request.user),
            pk=vendor_payment_id,
        )
        serializer = VendorPaymentWriteSerializer(payment, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        payment = serializer.save()
        return api_success(
            data=VendorPaymentSerializer(payment).data,
            message="Vendor payment updated successfully.",
        )

    def patch(self, request):
        vendor_payment_id, error_response = get_vendor_payment_id_param(request)
        if error_response:
            return error_response
        payment = get_object_or_404(
            get_vendor_payment_queryset(request.user),
            pk=vendor_payment_id,
        )
        serializer = VendorPaymentWriteSerializer(payment, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        payment = serializer.save()
        return api_success(
            data=VendorPaymentSerializer(payment).data,
            message="Vendor payment updated successfully.",
        )

    def delete(self, request):
        vendor_payment_id, error_response = get_vendor_payment_id_param(request)
        if error_response:
            return error_response
        payment = get_object_or_404(
            get_vendor_payment_queryset(request.user),
            pk=vendor_payment_id,
        )
        payment.delete()
        return api_success(message="Vendor payment deleted successfully.")
