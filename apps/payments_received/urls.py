from django.urls import path

from apps.payments_received.views import (
    PaymentReceivedApplyView,
    PaymentReceivedEmailView,
    PaymentReceivedExportView,
    PaymentReceivedFormView,
    PaymentReceivedHistoryView,
    PaymentReceivedOptionsView,
    PaymentReceivedPdfView,
    PaymentReceivedRefreshView,
    PaymentReceivedTemplateView,
    PaymentReceivedUnapplyView,
    PaymentReceivedView,
    PaymentReceivedVoidView,
)

urlpatterns = [
    path("", PaymentReceivedView.as_view(), name="payments-received"),
    path("options/", PaymentReceivedOptionsView.as_view(), name="payments-received-options"),
    path("form/", PaymentReceivedFormView.as_view(), name="payments-received-form"),
    path("refresh/", PaymentReceivedRefreshView.as_view(), name="payments-received-refresh"),
    path("export/", PaymentReceivedExportView.as_view(), name="payments-received-export"),
    path("apply/", PaymentReceivedApplyView.as_view(), name="payments-received-apply"),
    path("unapply/", PaymentReceivedUnapplyView.as_view(), name="payments-received-unapply"),
    path("history/", PaymentReceivedHistoryView.as_view(), name="payments-received-history"),
    path("void/", PaymentReceivedVoidView.as_view(), name="payments-received-void"),
    path("template/", PaymentReceivedTemplateView.as_view(), name="payments-received-template"),
    path("pdf/", PaymentReceivedPdfView.as_view(), name="payments-received-pdf"),
    path("email/", PaymentReceivedEmailView.as_view(), name="payments-received-email"),
]
