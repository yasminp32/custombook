from django.urls import path

from apps.time_entries.views import (
    TimeEntryExportView,
    TimeEntryFormView,
    TimeEntryOptionsView,
    TimeEntryRefreshView,
    TimeEntryView,
)

urlpatterns = [
    path("", TimeEntryView.as_view(), name="time-entries"),
    path("options/", TimeEntryOptionsView.as_view(), name="time-entry-options"),
    path("form/", TimeEntryFormView.as_view(), name="time-entry-form"),
    path("refresh/", TimeEntryRefreshView.as_view(), name="time-entry-refresh"),
    path("export/", TimeEntryExportView.as_view(), name="time-entry-export"),
]
