from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.countries import get_countries_list, get_states_for_country
from apps.accounts.responses import api_error, api_success
from apps.organizations.constants import (
    CURRENCY_OPTIONS,
    DATE_FORMAT_OPTIONS,
    FISCAL_YEAR_OPTIONS,
    INDUSTRY_OPTIONS,
    LANGUAGE_OPTIONS,
    LOCATION_OPTIONS,
    TIMEZONE_OPTIONS,
)
from apps.organizations.pagination import paginate_queryset
from apps.organizations.serializers import OrganizationSerializer, OrganizationSetupSerializer
from apps.organizations.services import get_current_organization, set_current_organization


def get_user_organization(user):
    return get_current_organization(user)


def organization_context(request, user=None):
    account = user or request.user
    current = get_current_organization(account)
    return {
        "request": request,
        "current_organization_id": current.id if current else None,
    }


def parse_organization_id(value):
    if value is None or str(value).strip() == "":
        return None, api_error(
            "organization_id is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        return UUID(str(value).strip()), None
    except (ValueError, AttributeError, TypeError):
        return None, api_error(
            "organization_id must be a valid UUID.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class OrganizationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organizations = request.user.owned_organizations.all().order_by("name")
        response = paginate_queryset(
            request,
            organizations,
            serializer=OrganizationSerializer,
            serializer_context=organization_context(request),
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        serializer = OrganizationSetupSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        organization, state_updated_from_gstin = serializer.create_organization(request.user)
        set_current_organization(request.user, organization)
        message = "Organization created successfully."
        if state_updated_from_gstin:
            message += " State was updated based on your GSTIN."
        return api_success(
            data=OrganizationSerializer(
                organization,
                context=organization_context(request),
            ).data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )


class OrganizationSetupOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "industries": INDUSTRY_OPTIONS,
                "locations": LOCATION_OPTIONS,
                "countries": get_countries_list(),
                "currencies": CURRENCY_OPTIONS,
                "languages": LANGUAGE_OPTIONS,
                "timezones": TIMEZONE_OPTIONS,
                "fiscal_years": FISCAL_YEAR_OPTIONS,
                "date_formats": DATE_FORMAT_OPTIONS,
            }
        )


class OrganizationCountryStatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, country_code):
        states = get_states_for_country(country_code)
        response = paginate_queryset(request, states)
        if response is not None:
            response.data["data"]["country"] = country_code.upper()
            return response

        return api_success(data={"country": country_code.upper(), "states": []})


class OrganizationMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = get_user_organization(request.user)
        if not organization:
            return api_error("Organization not found.", status_code=404)

        return api_success(
            data=OrganizationSerializer(
                organization,
                context=organization_context(request),
            ).data
        )

    def post(self, request):
        if get_user_organization(request.user):
            return api_error(
                "You already have an organization. Update or delete it before creating a new one.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrganizationSetupSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        organization, state_updated_from_gstin = serializer.create_organization(request.user)
        set_current_organization(request.user, organization)
        message = "Organization created successfully."
        if state_updated_from_gstin:
            message += " State was updated based on your GSTIN."

        return api_success(
            data=OrganizationSerializer(
                organization,
                context=organization_context(request),
            ).data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        organization = get_user_organization(request.user)
        if not organization:
            return api_error("Organization not found.", status_code=404)

        serializer = OrganizationSetupSerializer(
            data=request.data,
            partial=True,
            context={"request": request, "organization": organization},
        )
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        organization, state_updated_from_gstin = serializer.update_organization(organization)
        message = "Organization profile updated successfully."
        if state_updated_from_gstin:
            message += " State was updated based on your GSTIN."

        return api_success(
            data=OrganizationSerializer(
                organization,
                context=organization_context(request),
            ).data,
            message=message,
        )

    def delete(self, request):
        organization = get_user_organization(request.user)
        if not organization:
            return api_error("Organization not found.", status_code=status.HTTP_404_NOT_FOUND)

        organization.delete()
        request.user.refresh_from_db()
        fallback = get_current_organization(request.user)
        if fallback:
            set_current_organization(request.user, fallback)
        return api_success(
            message="Organization deleted successfully.",
            status_code=status.HTTP_200_OK,
        )


class OrganizationSwitchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_id = (
            request.query_params.get("organization_id")
            or request.query_params.get("id")
            or request.data.get("organization_id")
            or request.data.get("id")
        )
        organization_id, error_response = parse_organization_id(raw_id)
        if error_response:
            return error_response
        organization = request.user.owned_organizations.filter(pk=organization_id).first()
        if not organization:
            return api_error("Organization not found.", status_code=status.HTTP_404_NOT_FOUND)
        set_current_organization(request.user, organization)
        return api_success(
            data=OrganizationSerializer(
                organization,
                context=organization_context(request),
            ).data,
            message="Organization switched successfully.",
        )
