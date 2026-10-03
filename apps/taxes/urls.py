from django.urls import path

from apps.taxes.views import (
    TaxIndexView,
    TaxOptionsView,
    TaxPreferenceView,
    TaxRateView,
    TaxSettingsView,
)

urlpatterns = [
    path("", TaxIndexView.as_view(), name="taxes"),
    path("options/", TaxOptionsView.as_view(), name="tax-options"),
    path("rates/", TaxRateView.as_view(), name="tax-rates"),
    path("settings/", TaxSettingsView.as_view(), name="tax-settings"),
    path("preferences/", TaxPreferenceView.as_view(), name="tax-preferences"),
]
