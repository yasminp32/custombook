from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from apps.customers.models import Customer
from apps.dashboard.periods import get_period_range
from apps.invoices.models import Invoice
from apps.payments_received.models import PaymentReceived

ZERO = Decimal("0.00")
MONEY = Decimal("0.01")

ACTIVE_INVOICE = ~Q(status__in=(Invoice.Status.DRAFT, Invoice.Status.CANCELLED))
OPEN_INVOICE = ACTIVE_INVOICE & ~Q(status=Invoice.Status.PAID)


def money(value):
    amount = Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def _sum(queryset, field="amount"):
    total = queryset.aggregate(total=Coalesce(Sum(field), ZERO))["total"]
    return Decimal(total or 0)


def _period(organization, period):
    country = getattr(organization, "country", None) or "IN"
    key, label, start, end = get_period_range(period, country)
    return key, label, start, end


def _balance_due(total, paid):
    due = Decimal(total or 0) - Decimal(paid or 0)
    return due if due > 0 else ZERO


def run_report(organization, report_key, period="this_fiscal_year"):
    period_key, period_label, start, end = _period(organization, period)
    builders = {
        "balance_sheet": build_balance_sheet,
        "profit_and_loss": build_profit_and_loss,
        "cash_flow_statement": build_cash_flow,
        "sales_by_customer": build_sales_by_customer,
        "sales_by_item": build_sales_by_item,
        "sales_by_sales_person": build_sales_by_sales_person,
        "customer_balance_summary": build_customer_balance,
        "ar_aging_summary": build_ar_aging_summary,
        "ar_aging_details": build_ar_aging_details,
        "payments_received": build_payments_received,
        "expenses_by_category": build_expenses_by_category,
        "payments_made": build_payments_made,
        "vendor_balance_summary": build_vendor_balance,
    }
    builder = builders.get(report_key)
    data = builder(organization, start, end)
    data["period"] = period_key
    data["period_label"] = period_label
    data["date_from"] = start.isoformat()
    data["date_to"] = end.isoformat()
    return data


def build_balance_sheet(organization, start, end):
    from apps.reports.financial import build_balance_sheet_report

    return build_balance_sheet_report(
        organization,
        {
            "as_of_date": "today",
            "report_date": end.isoformat(),
            "report_basis": "accrual",
            "filter_accounts": "without_zero_balance",
            "compare_with": "none",
        },
    )


def build_profit_and_loss(organization, start, end):
    from apps.reports.financial import build_profit_and_loss_report

    return build_profit_and_loss_report(
        organization,
        {
            "date_range": "this_fiscal_year",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "report_basis": "accrual",
            "filter_accounts": "without_zero_balance",
            "compare_with": "none",
        },
    )


def build_cash_flow(organization, start, end):
    from apps.reports.financial import build_cash_flow_report

    return build_cash_flow_report(
        organization,
        {
            "date_range": "this_fiscal_year",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "report_basis": "cash",
            "filter_accounts": "without_zero_balance",
            "compare_with": "none",
        },
    )


def build_sales_by_customer(organization, start, end):
    from apps.reports.sales import build_sales_by_customer_report

    return build_sales_by_customer_report(
        organization,
        {
            "date_range": "custom",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
    )


def build_sales_by_item(organization, start, end):
    from apps.reports.sales import build_sales_by_item_report

    return build_sales_by_item_report(
        organization,
        {
            "date_range": "custom",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
    )


def build_sales_by_sales_person(organization, start, end):
    from apps.reports.sales import build_sales_by_sales_person_report

    return build_sales_by_sales_person_report(
        organization,
        {
            "date_range": "custom",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
    )


def build_customer_balance(organization, start, end):
    from apps.reports.receivables import build_customer_balance_summary_report

    return build_customer_balance_summary_report(
        organization,
        {
            "date_range": "custom",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
    )


def _aging_bucket(due_date, today):
    if not due_date:
        return "current"
    days = (today - due_date).days
    if days <= 0:
        return "current"
    if days <= 30:
        return "1_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "90_plus"


def build_ar_aging_summary(organization, start, end):
    from apps.reports.receivables import build_ar_aging_summary_report

    return build_ar_aging_summary_report(
        organization,
        {
            "as_of_date": "today",
            "report_date": end.isoformat(),
        },
    )


def build_ar_aging_details(organization, start, end):
    from apps.reports.receivables import build_ar_aging_details_report

    return build_ar_aging_details_report(
        organization,
        {
            "as_of_date": "today",
            "report_date": end.isoformat(),
        },
    )


def build_payments_received(organization, start, end):
    from apps.reports.receivables import build_payments_received_report

    return build_payments_received_report(
        organization,
        {
            "date_range": "custom",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
    )


def build_expenses_by_category(organization, start, end):
    from apps.reports.expenses import build_expenses_by_category_report

    return build_expenses_by_category_report(
        organization,
        {
            "date_range": "custom",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
    )


def build_payments_made(organization, start, end):
    from apps.reports.payables import build_payments_made_report

    return build_payments_made_report(
        organization,
        {
            "date_range": "custom",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
    )


def build_vendor_balance(organization, start, end):
    from apps.reports.payables import build_vendor_balance_summary_report

    return build_vendor_balance_summary_report(
        organization,
        {
            "date_range": "custom",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
    )
