from django.urls import path

from apps.currencies.views import CurrencyOptionsView, CurrencyView

urlpatterns = [
    path("", CurrencyView.as_view(), name="currencies"),
    path("options/", CurrencyOptionsView.as_view(), name="currency-options"),
]
