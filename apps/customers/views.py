from django.db import IntegrityError
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from uuid import UUID

from apps.accounts.countries import get_countries_list, get_states_for_country
from apps.accounts.responses import api_error, api_success
from apps.customers.address_filters import CustomerAddressFilter
from apps.customers.constants import (
    ACCOUNTS_RECEIVABLE,
    CUSTOMER_CURRENCIES,
    CUSTOMER_TYPES,
    PAYMENT_TERMS,
    PORTAL_LANGUAGES,
    SALUTATIONS,
    SOCIAL_PLATFORMS,
    TAX_TREATMENTS,
    choice_options,
)
from apps.customers.filters import CUSTOMER_FILTERS, CustomerFilter
from apps.customers.models import (
    Customer,
    CustomerAddress,
    CustomerContactPerson,
    CustomerPayment,
    CustomerSocialLink,
)
from apps.customers.payment_filters import CustomerPaymentFilter
from apps.customers.serializers import (
    CustomerAddressSerializer,
    CustomerAddressWriteSerializer,
    CustomerContactPersonSerializer,
    CustomerContactPersonWriteSerializer,
    CustomerPaymentSerializer,
    CustomerPaymentWriteSerializer,
    CustomerSerializer,
    CustomerSocialLinkSerializer,
    CustomerSocialLinkWriteSerializer,
    CustomerWriteSerializer,
)
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset
from apps.payment_terms.models import PaymentTerm

SORT_FIELDS = {
    "name": "display_name",
    "display_name": "display_name",
    "receivables": "receivables",
    "unused_credits": "unused_credits",
    "created_at": "created_at",
}


def parse_uuid(value, field_name="id"):
    if value is None or str(value).strip() == "":
        return None, api_error(
            f"{field_name} is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    raw = str(value).strip()
    if "{{" in raw or "}}" in raw:
        return None, api_error(
            f"{field_name} is still a Postman placeholder. "
            "Set the collection variable to the real UUID from create customer.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        return UUID(raw), None
    except (ValueError, AttributeError, TypeError):
        return None, api_error(
            f"{field_name} must be a valid UUID.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def get_owned_customer(user, customer_id, field_name="customer_id"):
    parsed_id, error_response = parse_uuid(customer_id, field_name)
    if error_response:
        return None, error_response
    customer = get_customer_queryset(user).filter(pk=parsed_id).first()
    if not customer:
        return None, api_error(
            "Customer not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return customer, None


def get_owned_object(queryset, object_id, field_name, not_found):
    parsed_id, error_response = parse_uuid(object_id, field_name)
    if error_response:
        return None, error_response
    obj = queryset.filter(pk=parsed_id).first()
    if not obj:
        return None, api_error(not_found, status_code=status.HTTP_404_NOT_FOUND)
    return obj, None


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_customer_queryset(user):
    return (
        Customer.objects.filter(organization__owner=user)
        .select_related("organization", "created_by")
        .prefetch_related(
            Prefetch(
                "addresses",
                queryset=CustomerAddress.objects.select_related("address"),
            ),
            "contact_persons",
            "social_links",
        )
    )


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_customer_id_param(request):
    customer_id = request.query_params.get("customer_id") or request.query_params.get("id")
    if not customer_id:
        return None, api_error(
            "customer_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    parsed_id, error_response = parse_uuid(customer_id, "customer_id")
    if error_response:
        return None, error_response
    return parsed_id, None


def apply_sorting(queryset, query_params):
    sort_by = (query_params.get("sort_by") or "name").strip().lower()
    sort_order = (query_params.get("sort_order") or "asc").strip().lower()
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
    return queryset.order_by(f"{prefix}{field}", "display_name"), None


def filtered_customer_queryset(request):
    queryset = get_customer_queryset(request.user)
    params = request.query_params.copy()
    if "filter" not in params and "status" not in params:
        params["filter"] = "active_customers"
    customer_filter = CustomerFilter(params, queryset=queryset)
    if not customer_filter.is_valid():
        return None, api_error("Invalid filter parameters.", errors=customer_filter.errors)
    queryset, error_response = apply_sorting(customer_filter.qs, request.query_params)
    if error_response:
        return None, error_response
    return queryset, None


class CustomerView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customer_id = request.query_params.get("customer_id") or request.query_params.get("id")
        if customer_id:
            customer, error_response = get_owned_customer(request.user, customer_id)
            if error_response:
                return error_response
            return api_success(data=CustomerSerializer(customer).data)

        queryset, error_response = filtered_customer_queryset(request)
        if error_response:
            return error_response

        response = paginate_queryset(
            request,
            queryset,
            serializer=CustomerSerializer,
        )
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
                "Organization not found. Complete organization setup before creating customers.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CustomerWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        created_by = serializer.validate_created_by_reference(request.user)
        customer = serializer.save(organization=organization, created_by=created_by)
        customer = get_customer_queryset(request.user).get(pk=customer.pk)
        return api_success(
            data=CustomerSerializer(customer).data,
            message="Customer created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        customer_id, error_response = get_customer_id_param(request)
        if error_response:
            return error_response

        customer, error_response = get_owned_customer(request.user, customer_id)
        if error_response:
            return error_response
        serializer = CustomerWriteSerializer(customer, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        customer = serializer.save()
        customer = get_customer_queryset(request.user).get(pk=customer.pk)
        return api_success(
            data=CustomerSerializer(customer).data,
            message="Customer updated successfully.",
        )

    def patch(self, request):
        customer_id, error_response = get_customer_id_param(request)
        if error_response:
            return error_response

        customer, error_response = get_owned_customer(request.user, customer_id)
        if error_response:
            return error_response
        serializer = CustomerWriteSerializer(customer, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        customer = serializer.save()
        customer = get_customer_queryset(request.user).get(pk=customer.pk)
        return api_success(
            data=CustomerSerializer(customer).data,
            message="Customer updated successfully.",
        )

    def delete(self, request):
        customer_id, error_response = get_customer_id_param(request)
        if error_response:
            return error_response

        customer, error_response = get_owned_customer(request.user, customer_id)
        if error_response:
            return error_response
        customer.delete()
        return api_success(message="Customer deleted successfully.")


class CustomerOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = resolve_organization(
            request.user,
            request.query_params.get("organization_id"),
        )
        organization_payment_terms = []
        if organization:
            organization_payment_terms = [
                {
                    "key": str(term.id),
                    "label": term.name,
                    "due_days": term.due_days,
                    "is_default": term.is_default,
                }
                for term in PaymentTerm.objects.filter(organization=organization)
            ]
        return api_success(
            data={
                "filters": [
                    {"key": key, "label": label} for key, label in CUSTOMER_FILTERS
                ],
                "sort_fields": [
                    {"key": "name", "label": "Name"},
                    {"key": "receivables", "label": "Receivables"},
                    {"key": "unused_credits", "label": "Unused Credits"},
                ],
                "statuses": [
                    {"key": key, "label": label} for key, label in Customer.Status.choices
                ],
                "customer_types": choice_options(CUSTOMER_TYPES),
                "salutations": choice_options(SALUTATIONS),
                "tax_treatments": choice_options(TAX_TREATMENTS),
                "places_of_supply": [
                    {"key": state, "label": state} for state in get_states_for_country("IN")
                ],
                "currencies": choice_options(CUSTOMER_CURRENCIES),
                "accounts_receivable": choice_options(ACCOUNTS_RECEIVABLE),
                "payment_terms": choice_options(PAYMENT_TERMS),
                "organization_payment_terms": organization_payment_terms,
                "portal_languages": choice_options(PORTAL_LANGUAGES),
                "social_platforms": choice_options(SOCIAL_PLATFORMS),
                "phone_country_codes": [
                    {
                        "key": country["phone_country_code"],
                        "label": f"{country['name']} ({country['phone_country_code']})",
                        "country": country["code"],
                    }
                    for country in get_countries_list()
                    if country.get("phone_country_code")
                ],
                "countries": get_countries_list(),
                "address_types": [
                    {"key": key, "label": label}
                    for key, label in CustomerAddress.AddressType.choices
                ],
                "actions": [
                    {"key": "refresh", "label": "Refresh", "path": "/api/customers/refresh/"},
                    {"key": "import", "label": "Import customers", "path": "/api/customers/import/"},
                    {"key": "export", "label": "Export customers", "path": "/api/customers/export/"},
                ],
            }
        )


class CustomerRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset, error_response = filtered_customer_queryset(request)
        if error_response:
            return error_response
        response = paginate_queryset(
            request,
            queryset,
            serializer=CustomerSerializer,
        )
        if response is not None:
            response.data["message"] = "Customers refreshed."
            return response
        return api_success(data=[], message="Customers refreshed.")


class CustomerExportView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # DRF uses ?format= to pick a renderer. csv is not a renderer here,
        # so leave negotiation alone and read format in get().
        renderer = self.get_renderers()[0]
        return (renderer, renderer.media_type)

    def get(self, request):
        queryset, error_response = filtered_customer_queryset(request)
        if error_response:
            return error_response
        rows = CustomerSerializer(queryset, many=True).data
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
                    "customer_id",
                    "name",
                    "display_name",
                    "email",
                    "phone",
                    "status",
                    "receivables",
                    "unused_credits",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "customer_id": row["customer_id"],
                        "name": row["name"],
                        "display_name": row["display_name"],
                        "email": row["email"],
                        "phone": row["phone"],
                        "status": row["status"],
                        "receivables": row["receivables"],
                        "unused_credits": row["unused_credits"],
                    }
                )
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="customers.csv"'
            return response
        return api_success(
            data={"count": len(rows), "customers": rows},
            message="Customers exported successfully.",
        )


class CustomerImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        organization = resolve_organization(
            request.user,
            request.data.get("organization_id") if hasattr(request.data, "get") else None,
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup before importing customers.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        payload = request.data.get("customers")
        if payload is None and request.FILES.get("file"):
            import csv
            import io

            uploaded = request.FILES["file"]
            try:
                decoded = uploaded.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                return api_error("Import file must be UTF-8 CSV.")
            reader = csv.DictReader(io.StringIO(decoded))
            payload = list(reader)

        if not isinstance(payload, list) or not payload:
            return api_error(
                "Provide customers as a JSON list or upload a CSV file.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        errors = []
        for index, row in enumerate(payload):
            serializer = CustomerWriteSerializer(data=row)
            if not serializer.is_valid():
                errors.append({"row": index + 1, "errors": serializer.errors})
                continue
            created_by = serializer.validate_created_by_reference(request.user)
            customer = serializer.save(organization=organization, created_by=created_by)
            created.append(CustomerSerializer(customer).data)

        return api_success(
            data={
                "created_count": len(created),
                "error_count": len(errors),
                "customers": created,
                "errors": errors,
            },
            message="Customer import completed.",
            status_code=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST,
        )


def get_contact_person_queryset(user):
    return CustomerContactPerson.objects.filter(
        customer__organization__owner=user,
    ).select_related("customer")


def get_contact_person_id_param(request):
    contact_person_id = (
        request.query_params.get("contact_person_id")
        or request.query_params.get("id")
    )
    if not contact_person_id:
        return None, api_error(
            "contact_person_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return parse_uuid(contact_person_id, "contact_person_id")


class CustomerContactPersonView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        contact_person_id = (
            request.query_params.get("contact_person_id")
            or request.query_params.get("id")
        )
        if contact_person_id:
            person, error_response = get_owned_object(
                get_contact_person_queryset(request.user),
                contact_person_id,
                "contact_person_id",
                "Contact person not found.",
            )
            if error_response:
                return error_response
            return api_success(data=CustomerContactPersonSerializer(person).data)

        queryset = get_contact_person_queryset(request.user)
        customer_id = request.query_params.get("customer_id")
        if customer_id:
            parsed_id, error_response = parse_uuid(customer_id, "customer_id")
            if error_response:
                return error_response
            queryset = queryset.filter(customer_id=parsed_id)

        response = paginate_queryset(
            request,
            queryset,
            serializer=CustomerContactPersonSerializer,
        )
        if response is not None:
            return response
        return api_success(data=[])

    def post(self, request):
        customer_id = request.data.get("customer_id")
        if not customer_id:
            return api_error("customer_id is required.", status_code=status.HTTP_400_BAD_REQUEST)

        customer, error_response = get_owned_customer(request.user, customer_id)
        if error_response:
            return error_response
        serializer = CustomerContactPersonWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        person = serializer.save(customer=customer)
        return api_success(
            data=CustomerContactPersonSerializer(person).data,
            message="Contact person added successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        contact_person_id, error_response = get_contact_person_id_param(request)
        if error_response:
            return error_response

        person, error_response = get_owned_object(
            get_contact_person_queryset(request.user),
            contact_person_id,
            "contact_person_id",
            "Contact person not found.",
        )
        if error_response:
            return error_response
        serializer = CustomerContactPersonWriteSerializer(person, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        person = serializer.save()
        return api_success(
            data=CustomerContactPersonSerializer(person).data,
            message="Contact person updated successfully.",
        )

    def patch(self, request):
        contact_person_id, error_response = get_contact_person_id_param(request)
        if error_response:
            return error_response

        person, error_response = get_owned_object(
            get_contact_person_queryset(request.user),
            contact_person_id,
            "contact_person_id",
            "Contact person not found.",
        )
        if error_response:
            return error_response
        serializer = CustomerContactPersonWriteSerializer(
            person,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        person = serializer.save()
        return api_success(
            data=CustomerContactPersonSerializer(person).data,
            message="Contact person updated successfully.",
        )

    def delete(self, request):
        contact_person_id, error_response = get_contact_person_id_param(request)
        if error_response:
            return error_response

        person, error_response = get_owned_object(
            get_contact_person_queryset(request.user),
            contact_person_id,
            "contact_person_id",
            "Contact person not found.",
        )
        if error_response:
            return error_response
        person.delete()
        return api_success(message="Contact person deleted successfully.")


def get_social_link_queryset(user):
    return CustomerSocialLink.objects.filter(
        customer__organization__owner=user,
    ).select_related("customer")


def get_social_link_id_param(request):
    social_link_id = (
        request.query_params.get("social_link_id")
        or request.query_params.get("id")
    )
    if not social_link_id:
        return None, api_error(
            "social_link_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return social_link_id, None


class CustomerSocialLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        social_link_id = (
            request.query_params.get("social_link_id")
            or request.query_params.get("id")
        )
        if social_link_id:
            link = get_object_or_404(
                get_social_link_queryset(request.user),
                pk=social_link_id,
            )
            return api_success(data=CustomerSocialLinkSerializer(link).data)

        queryset = get_social_link_queryset(request.user)
        customer_id = request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        response = paginate_queryset(
            request,
            queryset,
            serializer=CustomerSocialLinkSerializer,
        )
        if response is not None:
            return response
        return api_success(data=[])

    def post(self, request):
        customer_id = request.data.get("customer_id")
        if not customer_id:
            return api_error("customer_id is required.", status_code=status.HTTP_400_BAD_REQUEST)

        customer = get_object_or_404(get_customer_queryset(request.user), pk=customer_id)
        serializer = CustomerSocialLinkWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        link = serializer.save(customer=customer)
        return api_success(
            data=CustomerSocialLinkSerializer(link).data,
            message="Website / social link added successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        social_link_id, error_response = get_social_link_id_param(request)
        if error_response:
            return error_response

        link = get_object_or_404(
            get_social_link_queryset(request.user),
            pk=social_link_id,
        )
        serializer = CustomerSocialLinkWriteSerializer(link, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        link = serializer.save()
        return api_success(
            data=CustomerSocialLinkSerializer(link).data,
            message="Website / social link updated successfully.",
        )

    def patch(self, request):
        social_link_id, error_response = get_social_link_id_param(request)
        if error_response:
            return error_response

        link = get_object_or_404(
            get_social_link_queryset(request.user),
            pk=social_link_id,
        )
        serializer = CustomerSocialLinkWriteSerializer(
            link,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        link = serializer.save()
        return api_success(
            data=CustomerSocialLinkSerializer(link).data,
            message="Website / social link updated successfully.",
        )

    def delete(self, request):
        social_link_id, error_response = get_social_link_id_param(request)
        if error_response:
            return error_response

        link = get_object_or_404(
            get_social_link_queryset(request.user),
            pk=social_link_id,
        )
        link.delete()
        return api_success(message="Website / social link deleted successfully.")


def get_customer_address_queryset(user):
    return CustomerAddress.objects.filter(
        customer__organization__owner=user,
    ).select_related("customer", "address")


def get_customer_address_id_param(request):
    customer_address_id = (
        request.query_params.get("customer_address_id")
        or request.query_params.get("id")
    )
    if not customer_address_id:
        return None, api_error(
            "customer_address_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return customer_address_id, None


class CustomerAddressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customer_address_id = (
            request.query_params.get("customer_address_id")
            or request.query_params.get("id")
        )
        if customer_address_id:
            customer_address = get_object_or_404(
                get_customer_address_queryset(request.user),
                pk=customer_address_id,
            )
            return api_success(data=CustomerAddressSerializer(customer_address).data)

        queryset = get_customer_address_queryset(request.user)
        address_filter = CustomerAddressFilter(request.query_params, queryset=queryset)
        if not address_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=address_filter.errors)

        response = paginate_queryset(
            request,
            address_filter.qs,
            serializer=CustomerAddressSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        customer_id = request.data.get("customer_id")
        if not customer_id:
            return api_error("customer_id is required.", status_code=status.HTTP_400_BAD_REQUEST)

        customer = get_object_or_404(get_customer_queryset(request.user), pk=customer_id)
        serializer = CustomerAddressWriteSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            customer_address = serializer.save()
        except IntegrityError:
            return api_error(
                "This customer already has an address of this type.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_success(
            data=CustomerAddressSerializer(customer_address).data,
            message="Customer address created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        customer_address_id, error_response = get_customer_address_id_param(request)
        if error_response:
            return error_response

        customer_address = get_object_or_404(
            get_customer_address_queryset(request.user),
            pk=customer_address_id,
        )
        serializer = CustomerAddressWriteSerializer(
            customer_address,
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            customer_address = serializer.save()
        except IntegrityError:
            return api_error(
                "This customer already has an address of this type.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_success(
            data=CustomerAddressSerializer(customer_address).data,
            message="Customer address updated successfully.",
        )

    def patch(self, request):
        customer_address_id, error_response = get_customer_address_id_param(request)
        if error_response:
            return error_response

        customer_address = get_object_or_404(
            get_customer_address_queryset(request.user),
            pk=customer_address_id,
        )
        serializer = CustomerAddressWriteSerializer(
            customer_address,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            customer_address = serializer.save()
        except IntegrityError:
            return api_error(
                "This customer already has an address of this type.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_success(
            data=CustomerAddressSerializer(customer_address).data,
            message="Customer address updated successfully.",
        )

    def delete(self, request):
        customer_address_id, error_response = get_customer_address_id_param(request)
        if error_response:
            return error_response

        customer_address = get_object_or_404(
            get_customer_address_queryset(request.user),
            pk=customer_address_id,
        )
        customer_address.delete()
        return api_success(message="Customer address deleted successfully.")


def get_customer_payment_queryset(user):
    return CustomerPayment.objects.filter(
        organization__owner=user,
    ).select_related("organization", "customer")


def get_customer_payment_id_param(request):
    customer_payment_id = (
        request.query_params.get("customer_payment_id")
        or request.query_params.get("id")
    )
    if not customer_payment_id:
        return None, api_error(
            "customer_payment_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return customer_payment_id, None


class CustomerPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customer_payment_id = (
            request.query_params.get("customer_payment_id")
            or request.query_params.get("id")
        )
        if customer_payment_id:
            payment = get_object_or_404(
                get_customer_payment_queryset(request.user),
                pk=customer_payment_id,
            )
            return api_success(data=CustomerPaymentSerializer(payment).data)

        queryset = get_customer_payment_queryset(request.user)
        payment_filter = CustomerPaymentFilter(request.query_params, queryset=queryset)
        if not payment_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=payment_filter.errors)

        response = paginate_queryset(
            request,
            payment_filter.qs.order_by("-created_at"),
            serializer=CustomerPaymentSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        customer_id = request.data.get("customer_id")
        if not customer_id:
            return api_error("customer_id is required.", status_code=status.HTTP_400_BAD_REQUEST)

        get_object_or_404(get_customer_queryset(request.user), pk=customer_id)
        serializer = CustomerPaymentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            payment = serializer.save()
        except IntegrityError:
            return api_error(
                "Payment number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_success(
            data=CustomerPaymentSerializer(payment).data,
            message="Customer payment created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        customer_payment_id, error_response = get_customer_payment_id_param(request)
        if error_response:
            return error_response

        payment = get_object_or_404(
            get_customer_payment_queryset(request.user),
            pk=customer_payment_id,
        )
        serializer = CustomerPaymentWriteSerializer(payment, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            payment = serializer.save()
        except IntegrityError:
            return api_error(
                "Payment number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_success(
            data=CustomerPaymentSerializer(payment).data,
            message="Customer payment updated successfully.",
        )

    def patch(self, request):
        customer_payment_id, error_response = get_customer_payment_id_param(request)
        if error_response:
            return error_response

        payment = get_object_or_404(
            get_customer_payment_queryset(request.user),
            pk=customer_payment_id,
        )
        serializer = CustomerPaymentWriteSerializer(
            payment,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            payment = serializer.save()
        except IntegrityError:
            return api_error(
                "Payment number already exists for this organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_success(
            data=CustomerPaymentSerializer(payment).data,
            message="Customer payment updated successfully.",
        )

    def delete(self, request):
        customer_payment_id, error_response = get_customer_payment_id_param(request)
        if error_response:
            return error_response

        payment = get_object_or_404(
            get_customer_payment_queryset(request.user),
            pk=customer_payment_id,
        )
        payment.delete()
        return api_success(message="Customer payment deleted successfully.")
