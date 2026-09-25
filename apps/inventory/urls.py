from django.urls import path

from apps.inventory.views import (
    InventoryAdjustmentCommentView,
    InventoryAdjustmentOptionsView,
    InventoryAdjustmentPdfView,
    InventoryAdjustmentView,
)

urlpatterns = [
    path("adjustments/", InventoryAdjustmentView.as_view(), name="inventory-adjustments"),
    path(
        "adjustments/options/",
        InventoryAdjustmentOptionsView.as_view(),
        name="inventory-adjustment-options",
    ),
    path(
        "adjustments/comments/",
        InventoryAdjustmentCommentView.as_view(),
        name="inventory-adjustment-comments",
    ),
    path(
        "adjustments/pdf/",
        InventoryAdjustmentPdfView.as_view(),
        name="inventory-adjustment-pdf",
    ),
]
