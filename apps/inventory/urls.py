from django.urls import path

from apps.inventory.views import (
    InventoryAdjustmentOptionsView,
    InventoryAdjustmentView,
)

urlpatterns = [
    path("adjustments/", InventoryAdjustmentView.as_view(), name="inventory-adjustments"),
    path(
        "adjustments/options/",
        InventoryAdjustmentOptionsView.as_view(),
        name="inventory-adjustment-options",
    ),
]
