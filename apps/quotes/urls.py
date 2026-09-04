from django.urls import path

from apps.quotes.views import (
    QuoteExportView,
    QuoteOptionsView,
    QuoteRefreshView,
    QuoteSendView,
    QuoteView,
)

urlpatterns = [
    path("", QuoteView.as_view(), name="quotes"),
    path("options/", QuoteOptionsView.as_view(), name="quote-options"),
    path("refresh/", QuoteRefreshView.as_view(), name="quote-refresh"),
    path("export/", QuoteExportView.as_view(), name="quote-export"),
    path("send/", QuoteSendView.as_view(), name="quote-send"),
]
