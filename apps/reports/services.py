from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from apps.bills.models import Bill
from apps.customers.models import Customer
from apps.dashboard.periods import get_period_range
from apps.expenses.models import Expense
from apps.invoices.models import Invoice
from apps.payments_made.models import PaymentMade
from apps.payments_received.models import PaymentReceived
from apps.vendors.models import Vendor

ZERO = Decimal("0.00")
MONEY = Decimal("0.01")

ACTIVE_INVOICE = ~Q(status__in=(Invoice.Status.DRAFT, Invoice.Status.CANCELLED))
OPEN_INVOICE = ACTIVE_INVOICE & ~Q(status=Invoice.Status.PAID)
OPEN_BILL = ~Q(status__in=(Bill.Status.DRAFT, Bill.Status.PAID))


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
    queryset = (
        PaymentReceived.objects.filter(
            organization=organization,
            payment_date__range=(start, end),
        )
        .select_related("customer")
        .order_by("-payment_date")
    )
    rows = []
    for payment in queryset:
        name = ""
        if payment.customer:
            name = payment.customer.display_name or payment.customer.company_name or ""
        rows.append(
            {
                "payment_id": payment.id,
                "payment_number": payment.payment_number,
                "customer_name": name,
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "amount": money(payment.amount),
            }
        )
    return {"rows": rows, "total": money(_sum(queryset))}


def build_expenses_by_category(organization, start, end):
    rows = (
        Expense.objects.filter(
            organization=organization,
            expense_date__range=(start, end),
        )
        .values("category_id", "category__name")
        .annotate(amount=Coalesce(Sum("amount"), ZERO), expenses=Count("id"))
        .order_by("-amount")
    )
    results = []
    total = ZERO
    for row in rows:
        amount = Decimal(row["amount"] or 0)
        total += amount
        results.append(
            {
                "category_id": row["category_id"],
                "category_name": row["category__name"] or "Uncategorized",
                "expenses": row["expenses"],
                "amount": money(amount),
            }
        )
    return {"rows": results, "total": money(total)}


def build_payments_made(organization, start, end):
    queryset = (
        PaymentMade.objects.filter(
            organization=organization,
            payment_date__range=(start, end),
        )
        .select_related("vendor")
        .order_by("-payment_date")
    )
    rows = []
    for payment in queryset:
        name = ""
        if payment.vendor:
            name = payment.vendor.display_name or payment.vendor.company_name or ""
        rows.append(
            {
                "payment_id": payment.id,
                "payment_number": getattr(payment, "payment_number", ""),
                "vendor_name": name,
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "amount": money(payment.amount),
            }
        )
    return {"rows": rows, "total": money(_sum(queryset))}


def build_vendor_balance(organization, start, end):
    del start, end
    vendors = Vendor.objects.filter(organization=organization)
    bills = Bill.objects.filter(organization=organization).filter(OPEN_BILL)
    results = []
    total = ZERO
    for vendor in vendors:
        billed = ZERO
        paid = ZERO
        for bill in bills.filter(vendor=vendor):
            billed += Decimal(bill.amount or 0)
            paid += Decimal(bill.amount_paid or 0)
        opening = Decimal(vendor.opening_balance or 0)
        balance = opening + billed - paid
        if balance == 0 and billed == 0 and opening == 0:
            continue
        total += balance
        name = vendor.display_name or vendor.company_name or ""
        results.append(
            {
                "vendor_id": vendor.id,
                "vendor_name": name,
                "opening_balance": money(opening),
                "billed": money(billed),
                "paid": money(paid),
                "balance": money(balance),
            }
        )
    results.sort(key=lambda row: Decimal(row["balance"]), reverse=True)
    return {"rows": results, "total": money(total)}
