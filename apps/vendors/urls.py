from django.urls import path

from apps.vendors.views import VendorPaymentView, VendorView

urlpatterns = [
    path("", VendorView.as_view(), name="vendors"),
    path("payments/", VendorPaymentView.as_view(), name="vendor-payments"),
]