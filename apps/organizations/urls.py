from django.urls import path

from apps.organizations.views import (
    OrganizationCountryStatesView,
    OrganizationListView,
    OrganizationMeView,
    OrganizationSetupOptionsView,
)

urlpatterns = [
    path("", OrganizationListView.as_view(), name="organization-list"),
    path("setup-options/", OrganizationSetupOptionsView.as_view(), name="organization-setup-options"),
    path(
        "countries/<str:country_code>/states/",
        OrganizationCountryStatesView.as_view(),
        name="organization-country-states",
    ),
    path("me/", OrganizationMeView.as_view(), name="organization-me"),
]
