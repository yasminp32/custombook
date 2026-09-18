from django.urls import path

from apps.recurring_invoices.views import (
    RecurringInvoiceCommentView,
    RecurringInvoiceExportView,
    RecurringInvoiceFormView,
    RecurringInvoiceGenerateView,
    RecurringInvoiceOptionsView,
    RecurringInvoiceRefreshView,
    RecurringInvoiceResumeView,
    RecurringInvoiceStopView,
    RecurringInvoiceView,
)

urlpatterns = [
    path("", RecurringInvoiceView.as_view(), name="recurring-invoices"),
    path("options/", RecurringInvoiceOptionsView.as_view(), name="recurring-invoice-options"),
    path("form/", RecurringInvoiceFormView.as_view(), name="recurring-invoice-form"),
    path("refresh/", RecurringInvoiceRefreshView.as_view(), name="recurring-invoice-refresh"),
    path("export/", RecurringInvoiceExportView.as_view(), name="recurring-invoice-export"),
    path("stop/", RecurringInvoiceStopView.as_view(), name="recurring-invoice-stop"),
    path("resume/", RecurringInvoiceResumeView.as_view(), name="recurring-invoice-resume"),
    path("comments/", RecurringInvoiceCommentView.as_view(), name="recurring-invoice-comments"),
    path("generate/", RecurringInvoiceGenerateView.as_view(), name="recurring-invoice-generate"),
]
