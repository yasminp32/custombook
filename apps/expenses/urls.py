from django.urls import path

from apps.expenses.views import (
    ExpenseExportView,
    ExpenseFormView,
    ExpenseOptionsView,
    ExpenseRefreshView,
    ExpenseView,
)

urlpatterns = [
    path("", ExpenseView.as_view(), name="expenses"),
    path("options/", ExpenseOptionsView.as_view(), name="expense-options"),
    path("form/", ExpenseFormView.as_view(), name="expense-form"),
    path("refresh/", ExpenseRefreshView.as_view(), name="expense-refresh"),
    path("export/", ExpenseExportView.as_view(), name="expense-export"),
]
