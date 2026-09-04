from django.urls import path

from apps.customers.views import (
    CustomerAddressView,
    CustomerContactPersonView,
    CustomerExportView,
    CustomerImportView,
    CustomerOptionsView,
    CustomerPaymentView,
    CustomerRefreshView,
    CustomerSocialLinkView,
    CustomerView,
)

urlpatterns = [
    path("", CustomerView.as_view(), name="customers"),
    path("options/", CustomerOptionsView.as_view(), name="customer-options"),
    path("refresh/", CustomerRefreshView.as_view(), name="customer-refresh"),
    path("export/", CustomerExportView.as_view(), name="customer-export"),
    path("import/", CustomerImportView.as_view(), name="customer-import"),
    path("addresses/", CustomerAddressView.as_view(), name="customer-addresses"),
    path("contact-persons/", CustomerContactPersonView.as_view(), name="customer-contact-persons"),
    path("social-links/", CustomerSocialLinkView.as_view(), name="customer-social-links"),
    path("payments/", CustomerPaymentView.as_view(), name="customer-payments"),
]
