from django.urls import path

from apps.files.views import (
    FileDownloadView,
    FileFormView,
    FileOptionsView,
    FileRefreshView,
    FileShareView,
    FileSharedDownloadView,
    FileSharedView,
    FileView,
)

urlpatterns = [
    path("", FileView.as_view(), name="files"),
    path("options/", FileOptionsView.as_view(), name="files-options"),
    path("form/", FileFormView.as_view(), name="files-form"),
    path("refresh/", FileRefreshView.as_view(), name="files-refresh"),
    path("download/", FileDownloadView.as_view(), name="files-download"),
    path("share/", FileShareView.as_view(), name="files-share"),
    path("shared/<str:token>/", FileSharedView.as_view(), name="files-shared"),
    path(
        "shared/<str:token>/download/",
        FileSharedDownloadView.as_view(),
        name="files-shared-download",
    ),
]
