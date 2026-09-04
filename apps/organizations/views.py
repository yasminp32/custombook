from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.countries import get_countries_list, get_states_for_country
from apps.accounts.responses import api_error, api_success
from apps.organizations.constants import (
    CURRENCY_OPTIONS,
    INDUSTRY_OPTIONS,
    LANGUAGE_OPTIONS,
    TIMEZONE_OPTIONS,
)
from apps.organizations.pagination import paginate_queryset
from apps.organizations.serializers import OrganizationSerializer, OrganizationSetupSerializer


def get_user_organization(user):
    return user.owned_organizations.order_by("created_at").first()


class OrganizationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organizations = request.user.owned_organizations.all().order_by("-created_at")
        response = paginate_queryset(
            request,
            organizations,
            serializer=OrganizationSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])


class OrganizationSetupOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "industries": INDUSTRY_OPTIONS,
                "countries": get_countries_list(),
                "currencies": CURRENCY_OPTIONS,
                "languages": LANGUAGE_OPTIONS,
                "timezones": TIMEZONE_OPTIONS,
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

        return api_success(data=OrganizationSerializer(organization).data)

    def post(self, request):
        if get_user_organization(request.user):
            return api_error(
                "You already have an organization. Update or delete it before creating a new one.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrganizationSetupSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        organization, state_updated_from_gstin = serializer.create_organization(request.user)
        message = "Organization created successfully."
        if state_updated_from_gstin:
            message += " State was updated based on your GSTIN."

        return api_success(
            data=OrganizationSerializer(organization).data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        organization = get_user_organization(request.user)
        if not organization:
            return api_error("Organization not found.", status_code=404)

        serializer = OrganizationSetupSerializer(data=request.data, partial=False)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        organization, state_updated_from_gstin = serializer.update_organization(organization)
        message = "Organization profile updated successfully."
        if state_updated_from_gstin:
            message += " State was updated based on your GSTIN."

        return api_success(
            data=OrganizationSerializer(organization).data,
            message=message,
        )

    def delete(self, request):
        organization = get_user_organization(request.user)
        if not organization:
            return api_error("Organization not found.", status_code=status.HTTP_404_NOT_FOUND)

        organization.delete()
        return api_success(
            message="Organization deleted successfully.",
            status_code=status.HTTP_200_OK,
        )
