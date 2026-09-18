from django.urls import path

from apps.vendor_credits.views import (
    VendorCreditCloseView,
    VendorCreditExportView,
    VendorCreditFormView,
    VendorCreditOptionsView,
    VendorCreditRefreshView,
    VendorCreditView,
    VendorCreditVoidView,
)

urlpatterns = [
    path("", VendorCreditView.as_view(), name="vendor-credits"),
    path("options/", VendorCreditOptionsView.as_view(), name="vendor-credit-options"),
    path("form/", VendorCreditFormView.as_view(), name="vendor-credit-form"),
    path("refresh/", VendorCreditRefreshView.as_view(), name="vendor-credit-refresh"),
    path("export/", VendorCreditExportView.as_view(), name="vendor-credit-export"),
    path("close/", VendorCreditCloseView.as_view(), name="vendor-credit-close"),
    path("void/", VendorCreditVoidView.as_view(), name="vendor-credit-void"),
]
