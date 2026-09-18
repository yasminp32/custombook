from django.urls import path

from apps.bills.views import (
    BillExportView,
    BillFormView,
    BillMarkPaidView,
    BillMarkPartiallyPaidView,
    BillOptionsView,
    BillRefreshView,
    BillView,
)

urlpatterns = [
    path("", BillView.as_view(), name="bills"),
    path("options/", BillOptionsView.as_view(), name="bill-options"),
    path("form/", BillFormView.as_view(), name="bill-form"),
    path("refresh/", BillRefreshView.as_view(), name="bill-refresh"),
    path("export/", BillExportView.as_view(), name="bill-export"),
    path("mark-paid/", BillMarkPaidView.as_view(), name="bill-mark-paid"),
    path(
        "mark-partially-paid/",
        BillMarkPartiallyPaidView.as_view(),
        name="bill-mark-partially-paid",
    ),
]
