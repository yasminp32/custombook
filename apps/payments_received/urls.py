from django.urls import path

from apps.payments_received.views import (
    PaymentReceivedApplyView,
    PaymentReceivedExportView,
    PaymentReceivedFormView,
    PaymentReceivedOptionsView,
    PaymentReceivedRefreshView,
    PaymentReceivedUnapplyView,
    PaymentReceivedView,
)

urlpatterns = [
    path("", PaymentReceivedView.as_view(), name="payments-received"),
    path("options/", PaymentReceivedOptionsView.as_view(), name="payments-received-options"),
    path("form/", PaymentReceivedFormView.as_view(), name="payments-received-form"),
    path("refresh/", PaymentReceivedRefreshView.as_view(), name="payments-received-refresh"),
    path("export/", PaymentReceivedExportView.as_view(), name="payments-received-export"),
    path("apply/", PaymentReceivedApplyView.as_view(), name="payments-received-apply"),
    path("unapply/", PaymentReceivedUnapplyView.as_view(), name="payments-received-unapply"),
]
