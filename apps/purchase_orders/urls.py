from django.urls import path

from apps.purchase_orders.views import (
    PurchaseOrderCancelView,
    PurchaseOrderExportView,
    PurchaseOrderFormView,
    PurchaseOrderMarkBilledView,
    PurchaseOrderOptionsView,
    PurchaseOrderRefreshView,
    PurchaseOrderView,
)

urlpatterns = [
    path("", PurchaseOrderView.as_view(), name="purchase-orders"),
    path("options/", PurchaseOrderOptionsView.as_view(), name="purchase-order-options"),
    path("form/", PurchaseOrderFormView.as_view(), name="purchase-order-form"),
    path("refresh/", PurchaseOrderRefreshView.as_view(), name="purchase-order-refresh"),
    path("export/", PurchaseOrderExportView.as_view(), name="purchase-order-export"),
    path("mark-billed/", PurchaseOrderMarkBilledView.as_view(), name="purchase-order-mark-billed"),
    path("cancel/", PurchaseOrderCancelView.as_view(), name="purchase-order-cancel"),
]
