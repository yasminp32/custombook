from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.dashboard.periods import PERIOD_CHOICES
from apps.dashboard.services import (
    build_cash_flow,
    build_expense_breakdown,
    build_income_expense,
    build_overview,
    build_projects,
    build_support,
    build_updates,
)
from apps.organizations.models import Organization


def get_user_organization(user, organization_id=None):
    organizations = Organization.objects.filter(owner=user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def require_organization(request):
    organization = get_user_organization(
        request.user,
        request.query_params.get("organization_id"),
    )
    if not organization:
        return None, api_error(
            "Organization not found. Complete organization setup first.",
            status_code=400,
        )
    period = (request.query_params.get("period") or "this_fiscal_year").strip().lower()
    if period not in PERIOD_CHOICES:
        return None, api_error(
            "Invalid period.",
            errors={"period": f"Allowed values: {', '.join(PERIOD_CHOICES)}."},
        )
    return organization, None


class DashboardOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = require_organization(request)
        if error_response:
            return error_response
        return api_success(data=build_overview(organization, request.query_params))


class DashboardCashFlowView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = require_organization(request)
        if error_response:
            return error_response
        return api_success(data=build_cash_flow(organization, request.query_params))


class DashboardIncomeExpenseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = require_organization(request)
        if error_response:
            return error_response
        method = (request.query_params.get("accounting_method") or "accrual").lower()
        if method not in ("accrual", "cash"):
            return api_error(
                "Invalid accounting_method.",
                errors={"accounting_method": "Allowed values: accrual, cash."},
            )
        return api_success(data=build_income_expense(organization, request.query_params))


class DashboardProjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = require_organization(request)
        if error_response:
            return error_response
        return api_success(data=build_projects(organization, request.query_params))


class DashboardExpenseBreakdownView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = require_organization(request)
        if error_response:
            return error_response
        return api_success(data=build_expense_breakdown(organization, request.query_params))


class DashboardUpdatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = require_organization(request)
        if error_response:
            return error_response
        return api_success(data=build_updates(organization, request.query_params))


class DashboardSupportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = require_organization(request)
        if error_response:
            return error_response
        return api_success(data=build_support(organization, request.query_params))
