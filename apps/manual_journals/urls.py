from django.urls import path

from apps.manual_journals.views import (
    ManualJournalExportView,
    ManualJournalFormView,
    ManualJournalOptionsView,
    ManualJournalPublishView,
    ManualJournalRefreshView,
    ManualJournalView,
)

urlpatterns = [
    path("", ManualJournalView.as_view(), name="manual-journals"),
    path("options/", ManualJournalOptionsView.as_view(), name="manual-journal-options"),
    path("form/", ManualJournalFormView.as_view(), name="manual-journal-form"),
    path("refresh/", ManualJournalRefreshView.as_view(), name="manual-journal-refresh"),
    path("export/", ManualJournalExportView.as_view(), name="manual-journal-export"),
    path("publish/", ManualJournalPublishView.as_view(), name="manual-journal-publish"),
]
