from django.urls import path

from apps.dashboard.views import (
    DashboardCashFlowView,
    DashboardExpenseBreakdownView,
    DashboardIncomeExpenseView,
    DashboardOverviewView,
    DashboardProjectsView,
    DashboardSupportView,
    DashboardUpdatesView,
)

urlpatterns = [
    path("", DashboardOverviewView.as_view(), name="dashboard-overview"),
    path("cash-flow/", DashboardCashFlowView.as_view(), name="dashboard-cash-flow"),
    path("income-expense/", DashboardIncomeExpenseView.as_view(), name="dashboard-income-expense"),
    path("projects/", DashboardProjectsView.as_view(), name="dashboard-projects"),
    path("expenses/", DashboardExpenseBreakdownView.as_view(), name="dashboard-expenses"),
    path("updates/", DashboardUpdatesView.as_view(), name="dashboard-updates"),
    path("support/", DashboardSupportView.as_view(), name="dashboard-support"),
]
