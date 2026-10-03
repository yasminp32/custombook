from django.urls import path

from apps.preferences.views import (
    AddressPreviewView,
    BillsPreferenceView,
    CreditNotesPreferenceView,
    CustomFieldView,
    CustomersVendorsPreferenceView,
    ExpensesPreferenceView,
    GeneralPreferenceView,
    InvoicesPreferenceView,
    ItemsPreferenceView,
    MileageRateView,
    PreferenceIndexView,
    PreferenceOptionsView,
    PurchaseOrdersPreferenceView,
    QuotesPreferenceView,
    SalesOrdersPreferenceView,
    VendorPortalPreferenceView,
)

urlpatterns = [
    path("", PreferenceIndexView.as_view(), name="preferences"),
    path("options/", PreferenceOptionsView.as_view(), name="preference-options"),
    path("general/", GeneralPreferenceView.as_view(), name="preference-general"),
    path(
        "customers-vendors/",
        CustomersVendorsPreferenceView.as_view(),
        name="preference-customers-vendors",
    ),
    path("items/", ItemsPreferenceView.as_view(), name="preference-items"),
    path("quotes/", QuotesPreferenceView.as_view(), name="preference-quotes"),
    path("invoices/", InvoicesPreferenceView.as_view(), name="preference-invoices"),
    path("credit-notes/", CreditNotesPreferenceView.as_view(), name="preference-credit-notes"),
    path("sales-orders/", SalesOrdersPreferenceView.as_view(), name="preference-sales-orders"),
    path("expenses/", ExpensesPreferenceView.as_view(), name="preference-expenses"),
    path("bills/", BillsPreferenceView.as_view(), name="preference-bills"),
    path(
        "purchase-orders/",
        PurchaseOrdersPreferenceView.as_view(),
        name="preference-purchase-orders",
    ),
    path("vendor-portal/", VendorPortalPreferenceView.as_view(), name="preference-vendor-portal"),
    path("address-preview/", AddressPreviewView.as_view(), name="preference-address-preview"),
    path("custom-fields/", CustomFieldView.as_view(), name="preference-custom-fields"),
    path("mileage-rates/", MileageRateView.as_view(), name="preference-mileage-rates"),
]
