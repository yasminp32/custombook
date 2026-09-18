from django.urls import path

from apps.credit_notes.views import (
    CreditNoteCloseView,
    CreditNoteExportView,
    CreditNoteFormView,
    CreditNoteOptionsView,
    CreditNoteRefreshView,
    CreditNoteView,
    CreditNoteVoidView,
)

urlpatterns = [
    path("", CreditNoteView.as_view(), name="credit-notes"),
    path("options/", CreditNoteOptionsView.as_view(), name="credit-note-options"),
    path("form/", CreditNoteFormView.as_view(), name="credit-note-form"),
    path("refresh/", CreditNoteRefreshView.as_view(), name="credit-note-refresh"),
    path("export/", CreditNoteExportView.as_view(), name="credit-note-export"),
    path("close/", CreditNoteCloseView.as_view(), name="credit-note-close"),
    path("void/", CreditNoteVoidView.as_view(), name="credit-note-void"),
]
