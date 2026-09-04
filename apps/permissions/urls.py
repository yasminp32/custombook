from django.urls import path

from apps.permissions.views import PermissionView

urlpatterns = [
    path("", PermissionView.as_view(), name="permissions"),
]
