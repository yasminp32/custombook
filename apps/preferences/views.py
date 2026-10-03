from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.customers.models import Customer
from apps.preferences import constants
from apps.preferences.models import CustomField, MileageRate
from apps.preferences.serializers import (
    AddressPreviewSerializer,
    CustomFieldSerializer,
    CustomFieldWriteSerializer,
    CustomersVendorsPreferenceSerializer,
    ExpensesPreferenceSerializer,
    FieldsOnlyPreferenceSerializer,
    GeneralPreferenceSerializer,
    InvoicesPreferenceSerializer,
    ItemsPreferenceSerializer,
    MileageRateSerializer,
    MileageRateWriteSerializer,
    QuotesPreferenceSerializer,
    VendorPortalPreferenceSerializer,
)
from apps.preferences.services import (
    contact_placeholder_values,
    get_or_create_preference,
    organization_placeholder_values,
    render_address,
    resolve_organization,
)
from apps.vendors.models import Vendor

NO_ORGANIZATION_MESSAGE = "Organization not found. Complete organization setup first."


def organization_id_from(request):
    return request.query_params.get("organization_id") or request.data.get("organization_id")


def load_preference(request):
    organization = resolve_organization(request.user, organization_id_from(request))
    if not organization:
        return None, None, api_error(NO_ORGANIZATION_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)
    return organization, get_or_create_preference(organization), None


class PreferenceIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, _preference, error = load_preference(request)
        if error:
            return error
        sections = []
        for code, label in constants.SECTIONS:
            path = code.replace("_", "-")
            sections.append(
                {
                    "code": code,
                    "label": label,
                    "url": request.build_absolute_uri(f"/api/preferences/{path}/"),
                }
            )
        return api_success(
            data={
                "organization_id": str(organization.id),
                "organization_name": organization.name,
                "sections": sections,
            }
        )


class PreferenceOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "modules": constants.options_payload(constants.MODULE_OPTIONS),
                "discount_types": constants.options_payload(constants.DISCOUNT_TYPE_OPTIONS),
                "tax_types": constants.options_payload(constants.TAX_TYPE_OPTIONS),
                "rounding": constants.options_payload(constants.ROUNDING_OPTIONS),
                "customer_types": constants.options_payload(constants.CUSTOMER_TYPE_OPTIONS),
                "mileage_units": constants.options_payload(constants.MILEAGE_UNIT_OPTIONS),
                "mileage_categories": constants.options_payload(constants.MILEAGE_CATEGORY_OPTIONS),
                "custom_field_entities": constants.options_payload(constants.CUSTOM_FIELD_ENTITIES),
                "custom_field_data_types": constants.options_payload(constants.CUSTOM_FIELD_DATA_TYPES),
                "organization_placeholders": [
                    {"label": label, "value": value}
                    for label, value in constants.ORGANIZATION_PLACEHOLDERS
                ],
                "contact_placeholders": [
                    {"label": label, "value": value}
                    for label, value in constants.CONTACT_PLACEHOLDERS
                ],
                "defaults": {
                    "organization_address_format": constants.DEFAULT_ORGANIZATION_ADDRESS_FORMAT,
                    "billing_address_format": constants.DEFAULT_BILLING_ADDRESS_FORMAT,
                    "shipping_address_format": constants.DEFAULT_SHIPPING_ADDRESS_FORMAT,
                },
            }
        )


class PreferenceSectionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = None
    section_label = ""

    def get(self, request):
        _organization, preference, error = load_preference(request)
        if error:
            return error
        return api_success(data=self.serializer_class(preference).data)

    def put(self, request):
        return self._save(request, partial=False)

    def patch(self, request):
        return self._save(request, partial=True)

    def _save(self, request, partial):
        _organization, preference, error = load_preference(request)
        if error:
            return error
        serializer = self.serializer_class(preference, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        preference = serializer.save()
        return api_success(
            data=self.serializer_class(preference).data,
            message=f"{self.section_label} preferences saved.",
        )


class GeneralPreferenceView(PreferenceSectionView):
    serializer_class = GeneralPreferenceSerializer
    section_label = "General"


class CustomersVendorsPreferenceView(PreferenceSectionView):
    serializer_class = CustomersVendorsPreferenceSerializer
    section_label = "Customers and vendors"


class ItemsPreferenceView(PreferenceSectionView):
    serializer_class = ItemsPreferenceSerializer
    section_label = "Item"


class QuotesPreferenceView(PreferenceSectionView):
    serializer_class = QuotesPreferenceSerializer
    section_label = "Quote"


class InvoicesPreferenceView(PreferenceSectionView):
    serializer_class = InvoicesPreferenceSerializer
    section_label = "Invoice"


class ExpensesPreferenceView(PreferenceSectionView):
    serializer_class = ExpensesPreferenceSerializer
    section_label = "Expense"


class VendorPortalPreferenceView(PreferenceSectionView):
    serializer_class = VendorPortalPreferenceSerializer
    section_label = "Vendor portal"


class FieldsOnlySectionView(APIView):
    permission_classes = [IsAuthenticated]
    entity = ""

    def get(self, request):
        _organization, preference, error = load_preference(request)
        if error:
            return error
        serializer = FieldsOnlyPreferenceSerializer(preference)
        serializer.entity = self.entity
        return api_success(data=serializer.data)


class CreditNotesPreferenceView(FieldsOnlySectionView):
    entity = "credit_notes"


class SalesOrdersPreferenceView(FieldsOnlySectionView):
    entity = "sales_orders"


class BillsPreferenceView(FieldsOnlySectionView):
    entity = "bills"


class PurchaseOrdersPreferenceView(FieldsOnlySectionView):
    entity = "purchase_orders"


class AddressPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, preference, error = load_preference(request)
        if error:
            return error
        serializer = AddressPreviewSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        payload = serializer.validated_data
        preview_type = payload.get("type") or "organization"
        template = payload.get("format")

        if preview_type == "organization":
            if template is None:
                template = preference.organization_address_format
            values = organization_placeholder_values(organization)
        else:
            if template is None:
                template = (
                    preference.billing_address_format
                    if preview_type == "billing"
                    else preference.shipping_address_format
                )
            customer = vendor = None
            if payload.get("customer_id"):
                customer = get_object_or_404(
                    Customer.objects.filter(organization=organization), pk=payload["customer_id"]
                )
            elif payload.get("vendor_id"):
                vendor = get_object_or_404(
                    Vendor.objects.filter(organization=organization), pk=payload["vendor_id"]
                )
            values = contact_placeholder_values(
                customer=customer,
                vendor=vendor,
                address_type=preview_type,
                organization=organization,
            )

        rendered = render_address(template, values)
        return api_success(
            data={
                "type": preview_type,
                "format": template,
                "preview": rendered,
                "lines": rendered.split("\n") if rendered else [],
            }
        )


def get_id_param(request, *names):
    for name in names:
        value = request.query_params.get(name)
        if value:
            return value, None
    return None, api_error(
        f"{names[0]} query parameter is required.",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


class CustomFieldView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        return CustomField.objects.filter(organization__owner=request.user)

    def get(self, request):
        field_id = request.query_params.get("field_id") or request.query_params.get("id")
        if field_id:
            field = get_object_or_404(self.get_queryset(request), pk=field_id)
            return api_success(data=CustomFieldSerializer(field).data)

        organization, _preference, error = load_preference(request)
        if error:
            return error
        queryset = CustomField.objects.filter(organization=organization)
        entity = request.query_params.get("entity")
        if entity:
            if entity not in dict(constants.CUSTOM_FIELD_ENTITIES):
                return api_error(
                    "Invalid entity. Allowed values: "
                    + ", ".join(code for code, _label in constants.CUSTOM_FIELD_ENTITIES)
                    + ".",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(entity=entity)
        is_active = request.query_params.get("is_active")
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=(is_active == "true"))
        return api_success(
            data={
                "entity": entity or "",
                "count": queryset.count(),
                "results": CustomFieldSerializer(queryset, many=True).data,
            }
        )

    def post(self, request):
        organization, _preference, error = load_preference(request)
        if error:
            return error
        serializer = CustomFieldWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        data = serializer.validated_data
        if CustomField.objects.filter(
            organization=organization, entity=data["entity"], label__iexact=data["label"]
        ).exists():
            return api_error("A field with this label already exists for this module.")
        if "sort_order" not in data:
            data["sort_order"] = (
                CustomField.objects.filter(organization=organization, entity=data["entity"]).count()
                + 1
            )
        try:
            field = serializer.save(organization=organization)
        except IntegrityError:
            return api_error("A field with this label already exists for this module.")
        return api_success(
            data=CustomFieldSerializer(field).data,
            message="Custom field added.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        field_id, error = get_id_param(request, "field_id", "id")
        if error:
            return error
        field = get_object_or_404(self.get_queryset(request), pk=field_id)
        serializer = CustomFieldWriteSerializer(field, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        data = serializer.validated_data
        entity = data.get("entity", field.entity)
        label = data.get("label", field.label)
        if (
            CustomField.objects.filter(
                organization=field.organization, entity=entity, label__iexact=label
            )
            .exclude(pk=field.pk)
            .exists()
        ):
            return api_error("A field with this label already exists for this module.")
        try:
            field = serializer.save()
        except IntegrityError:
            return api_error("A field with this label already exists for this module.")
        return api_success(data=CustomFieldSerializer(field).data, message="Custom field updated.")

    def delete(self, request):
        field_id, error = get_id_param(request, "field_id", "id")
        if error:
            return error
        field = get_object_or_404(self.get_queryset(request), pk=field_id)
        field.delete()
        return api_success(message="Custom field deleted.")


class MileageRateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        return MileageRate.objects.filter(organization__owner=request.user)

    def get(self, request):
        rate_id = request.query_params.get("rate_id") or request.query_params.get("id")
        if rate_id:
            rate = get_object_or_404(self.get_queryset(request), pk=rate_id)
            return api_success(data=MileageRateSerializer(rate).data)
        organization, preference, error = load_preference(request)
        if error:
            return error
        rates = MileageRate.objects.filter(organization=organization)
        return api_success(
            data={
                "unit": preference.mileage_unit,
                "unit_label": preference.get_mileage_unit_display(),
                "count": rates.count(),
                "results": MileageRateSerializer(rates, many=True).data,
            }
        )

    def post(self, request):
        organization, _preference, error = load_preference(request)
        if error:
            return error
        serializer = MileageRateWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        if MileageRate.objects.filter(
            organization=organization, start_date=serializer.validated_data["start_date"]
        ).exists():
            return api_error("A mileage rate already exists for this start date.")
        rate = serializer.save(organization=organization)
        return api_success(
            data=MileageRateSerializer(rate).data,
            message="Mileage rate added.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        rate_id, error = get_id_param(request, "rate_id", "id")
        if error:
            return error
        rate = get_object_or_404(self.get_queryset(request), pk=rate_id)
        serializer = MileageRateWriteSerializer(rate, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        start_date = serializer.validated_data.get("start_date", rate.start_date)
        if (
            MileageRate.objects.filter(organization=rate.organization, start_date=start_date)
            .exclude(pk=rate.pk)
            .exists()
        ):
            return api_error("A mileage rate already exists for this start date.")
        rate = serializer.save()
        return api_success(data=MileageRateSerializer(rate).data, message="Mileage rate updated.")

    def delete(self, request):
        rate_id, error = get_id_param(request, "rate_id", "id")
        if error:
            return error
        rate = get_object_or_404(self.get_queryset(request), pk=rate_id)
        rate.delete()
        return api_success(message="Mileage rate deleted.")
