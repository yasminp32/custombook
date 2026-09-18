from django.urls import path

from apps.delivery_challans.views import (
    DeliveryChallanCancelView,
    DeliveryChallanDeliverView,
    DeliveryChallanExportView,
    DeliveryChallanFormView,
    DeliveryChallanOptionsView,
    DeliveryChallanRefreshView,
    DeliveryChallanReturnView,
    DeliveryChallanView,
)

urlpatterns = [
    path("", DeliveryChallanView.as_view(), name="delivery-challans"),
    path("options/", DeliveryChallanOptionsView.as_view(), name="delivery-challan-options"),
    path("form/", DeliveryChallanFormView.as_view(), name="delivery-challan-form"),
    path("refresh/", DeliveryChallanRefreshView.as_view(), name="delivery-challan-refresh"),
    path("export/", DeliveryChallanExportView.as_view(), name="delivery-challan-export"),
    path("deliver/", DeliveryChallanDeliverView.as_view(), name="delivery-challan-deliver"),
    path("return/", DeliveryChallanReturnView.as_view(), name="delivery-challan-return"),
    path("cancel/", DeliveryChallanCancelView.as_view(), name="delivery-challan-cancel"),
]
