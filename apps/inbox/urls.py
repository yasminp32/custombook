from django.urls import path

from apps.inbox.views import (
    InboxDownloadView,
    InboxFormView,
    InboxOptionsView,
    InboxRefreshView,
    InboxShareView,
    InboxSharedDownloadView,
    InboxSharedView,
    InboxView,
)

urlpatterns = [
    path("", InboxView.as_view(), name="inbox"),
    path("options/", InboxOptionsView.as_view(), name="inbox-options"),
    path("form/", InboxFormView.as_view(), name="inbox-form"),
    path("refresh/", InboxRefreshView.as_view(), name="inbox-refresh"),
    path("download/", InboxDownloadView.as_view(), name="inbox-download"),
    path("share/", InboxShareView.as_view(), name="inbox-share"),
    path("shared/<str:token>/", InboxSharedView.as_view(), name="inbox-shared"),
    path(
        "shared/<str:token>/download/",
        InboxSharedDownloadView.as_view(),
        name="inbox-shared-download",
    ),
]
