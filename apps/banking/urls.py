from django.urls import path

from apps.banking.views import (
    BankAccountView,
    BankingOptionsView,
    BankingOverviewView,
    BankingRefreshView,
    BankingStatementExportView,
    BankTransactionView,
)

urlpatterns = [
    path("overview/", BankingOverviewView.as_view(), name="banking-overview"),
    path("refresh/", BankingRefreshView.as_view(), name="banking-refresh"),
    path("accounts/", BankAccountView.as_view(), name="bank-accounts"),
    path("transactions/", BankTransactionView.as_view(), name="bank-transactions"),
    path("statements/export/", BankingStatementExportView.as_view(), name="banking-statement-export"),
    path("options/", BankingOptionsView.as_view(), name="banking-options"),
]
