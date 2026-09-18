from django.urls import path

from apps.folders.views import FolderFormView, FolderOptionsView, FolderView

urlpatterns = [
    path("", FolderView.as_view(), name="folders"),
    path("options/", FolderOptionsView.as_view(), name="folders-options"),
    path("form/", FolderFormView.as_view(), name="folders-form"),
]
