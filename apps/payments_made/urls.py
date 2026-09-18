from django.urls import path

from apps.payments_made.views import (
    PaymentMadeExportView,
    PaymentMadeFormView,
    PaymentMadeOptionsView,
    PaymentMadeRefreshView,
    PaymentMadeView,
)

urlpatterns = [
    path("", PaymentMadeView.as_view(), name="payments-made"),
    path("options/", PaymentMadeOptionsView.as_view(), name="payments-made-options"),
    path("form/", PaymentMadeFormView.as_view(), name="payments-made-form"),
    path("refresh/", PaymentMadeRefreshView.as_view(), name="payments-made-refresh"),
    path("export/", PaymentMadeExportView.as_view(), name="payments-made-export"),
]
