from django.urls import path

from apps.sales_orders.views import (
    SalesOrderCancelView,
    SalesOrderConfirmView,
    SalesOrderExportView,
    SalesOrderFormView,
    SalesOrderMarkInvoicedView,
    SalesOrderOptionsView,
    SalesOrderRefreshView,
    SalesOrderView,
)

urlpatterns = [
    path("", SalesOrderView.as_view(), name="sales-orders"),
    path("options/", SalesOrderOptionsView.as_view(), name="sales-order-options"),
    path("form/", SalesOrderFormView.as_view(), name="sales-order-form"),
    path("refresh/", SalesOrderRefreshView.as_view(), name="sales-order-refresh"),
    path("export/", SalesOrderExportView.as_view(), name="sales-order-export"),
    path("confirm/", SalesOrderConfirmView.as_view(), name="sales-order-confirm"),
    path("cancel/", SalesOrderCancelView.as_view(), name="sales-order-cancel"),
    path(
        "mark-invoiced/",
        SalesOrderMarkInvoicedView.as_view(),
        name="sales-order-mark-invoiced",
    ),
]
