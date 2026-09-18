from django.urls import path

from apps.invoices.views import (
    InvoiceCancelView,
    InvoiceExportView,
    InvoiceFormView,
    InvoiceMarkPaidView,
    InvoiceMarkPartiallyPaidView,
    InvoiceOptionsView,
    InvoiceRefreshView,
    InvoiceSendView,
    InvoiceView,
)

urlpatterns = [
    path("", InvoiceView.as_view(), name="invoices"),
    path("options/", InvoiceOptionsView.as_view(), name="invoice-options"),
    path("form/", InvoiceFormView.as_view(), name="invoice-form"),
    path("refresh/", InvoiceRefreshView.as_view(), name="invoice-refresh"),
    path("export/", InvoiceExportView.as_view(), name="invoice-export"),
    path("send/", InvoiceSendView.as_view(), name="invoice-send"),
    path("mark-paid/", InvoiceMarkPaidView.as_view(), name="invoice-mark-paid"),
    path(
        "mark-partially-paid/",
        InvoiceMarkPartiallyPaidView.as_view(),
        name="invoice-mark-partially-paid",
    ),
    path("cancel/", InvoiceCancelView.as_view(), name="invoice-cancel"),
]
