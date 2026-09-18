from django.urls import path

from apps.vendors.views import (
    VendorExportView,
    VendorFormView,
    VendorImportView,
    VendorOptionsView,
    VendorPaymentView,
    VendorRefreshView,
    VendorView,
)

urlpatterns = [
    path("", VendorView.as_view(), name="vendors"),
    path("options/", VendorOptionsView.as_view(), name="vendor-options"),
    path("form/", VendorFormView.as_view(), name="vendor-form"),
    path("refresh/", VendorRefreshView.as_view(), name="vendor-refresh"),
    path("export/", VendorExportView.as_view(), name="vendor-export"),
    path("import/", VendorImportView.as_view(), name="vendor-import"),
    path("payments/", VendorPaymentView.as_view(), name="vendor-payments"),
]
