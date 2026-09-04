from django.urls import path

from apps.items.views import ItemOptionsView, ItemView

urlpatterns = [
    path("", ItemView.as_view(), name="items"),
    path("options/", ItemOptionsView.as_view(), name="item-options"),
]
