from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.customers.models import Customer, CustomerPayment
from apps.dashboard.periods import PERIOD_CHOICES, PERIOD_LABELS, get_period_range, month_points_for_range
from apps.vendors.models import Vendor, VendorPayment

ZERO = Decimal("0.00")

QUICK_ACTIONS = [
    {"key": "new_customer", "label": "New Customer", "path": "/api/customers/"},
    {"key": "new_invoice", "label": "New Invoice", "path": None},
    {"key": "new_bill", "label": "New Bill", "path": None},
    {"key": "new_expense", "label": "New Expense", "path": None},
]

DASHBOARD_TABS = [
    {"key": "overview", "label": "Overview", "path": "/api/dashboard/"},
    {"key": "updates", "label": "Updates", "path": "/api/dashboard/updates/"},
    {"key": "support", "label": "Support", "path": "/api/dashboard/support/"},
]

UPDATE_ITEMS = [
    {
        "key": "automated_invoicing",
        "type": "feature",
        "icon": "party_popper",
        "title": "New Feature: Automated Invoicing",
        "description": (
            "Save time with our new automated invoicing system. "
            "Schedule recurring invoices and never miss a payment."
        ),
        "age": timedelta(hours=2),
        "is_read": False,
    },
    {
        "key": "system_maintenance",
        "type": "maintenance",
        "icon": "wrench",
        "title": "System Maintenance Scheduled",
        "description": (
            "We will be performing system maintenance on Saturday, 8 PM - 10 PM. "
            "Services may be temporarily unavailable."
        ),
        "age": timedelta(days=1),
        "is_read": False,
    },
    {
        "key": "tax_season",
        "type": "reminder",
        "icon": "calendar",
        "title": "Tax Season Reminder",
        "description": (
            "Tax season is approaching. Ensure all your financial records are "
            "up to date and consult with your accountant."
        ),
        "age": timedelta(days=3),
        "is_read": False,
    },
    {
        "key": "payment_gateway",
        "type": "integration",
        "icon": "credit_card",
        "title": "New Payment Gateway Integration",
        "description": (
            "We have added support for multiple payment gateways. "
            "Check settings to configure your preferred payment method."
        ),
        "age": timedelta(days=5),
        "is_read": False,
    },
]

SUPPORT_CATEGORIES = [
    {
        "key": "getting_started",
        "icon": "rocket",
        "title": "Getting Started",
        "description": "Learn the basics of using Own Store",
        "items": [
            {"key": "first_invoice", "label": "Creating your first invoice", "path": None},
            {"key": "customers_vendors", "label": "Adding customers and vendors", "path": None},
            {"key": "payment_methods", "label": "Setting up payment methods", "path": None},
            {"key": "understanding_dashboard", "label": "Understanding the dashboard", "path": None},
        ],
    },
    {
        "key": "financial_reports",
        "icon": "bar_chart",
        "title": "Financial Reports",
        "description": "Generate and understand reports",
        "items": [
            {"key": "cash_flow_statements", "label": "Cash flow statements", "path": "/api/dashboard/cash-flow/"},
            {
                "key": "income_expense_reports",
                "label": "Income and expense reports",
                "path": "/api/dashboard/income-expense/",
            },
            {"key": "tax_preparation_reports", "label": "Tax preparation reports", "path": None},
            {"key": "custom_report_builder", "label": "Custom report builder", "path": None},
        ],
    },
    {
        "key": "account_management",
        "icon": "settings",
        "title": "Account Management",
        "description": "Manage your account settings",
        "items": [
            {"key": "update_profile", "label": "Update profile information", "path": "/api/accounts/me/"},
            {"key": "change_password", "label": "Change password", "path": "/api/accounts/reset-password/"},
            {"key": "notification_preferences", "label": "Notification preferences", "path": None},
            {"key": "subscription_billing", "label": "Subscription and billing", "path": None},
        ],
    },
]

SUPPORT_CONTACT = {
    "heading": "Still need help?",
    "subheading": "Contact our support team",
    "button_label": "Contact Support",
    "path": None,
}

EXPENSE_COLORS = [
    "#2563EB",
    "#7C3AED",
    "#16A34A",
    "#F97316",
    "#DC2626",
    "#64748B",
]


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def _sum(queryset, field="amount"):
    return queryset.aggregate(total=Coalesce(Sum(field), ZERO))["total"] or ZERO


def available_periods():
    return [{"key": key, "label": PERIOD_LABELS[key]} for key in PERIOD_CHOICES]


def relative_time(published_at, now=None):
    now = now or timezone.now()
    seconds = max(int((now - published_at).total_seconds()), 0)
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {unit} ago"
    hours = minutes // 60
    if hours < 24:
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit} ago"
    days = hours // 24
    if days < 7:
        unit = "day" if days == 1 else "days"
        return f"{days} {unit} ago"
    weeks = days // 7
    if weeks < 5:
        unit = "week" if weeks == 1 else "weeks"
        return f"{weeks} {unit} ago"
    return published_at.date().isoformat()


def dashboard_header(context, active_tab):
    return {
        "title": "Business Overview",
        "snapshot_label": "Snapshot",
        "tabs": DASHBOARD_TABS,
        "active_tab": active_tab,
    }


def resolve_period(organization, query_params):
    period, label, start, end = get_period_range(
        query_params.get("period"),
        country_code=getattr(organization, "country", "IN"),
    )
    return {
        "period": period,
        "period_label": label,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "start": start,
        "end": end,
        "currency": organization.currency or "INR",
        "accounting_method": (query_params.get("accounting_method") or "accrual").lower(),
    }


def _customer_payments(organization, start=None, end=None):
    queryset = CustomerPayment.objects.filter(organization=organization)
    if start and end:
        queryset = queryset.filter(payment_date__range=(start, end))
    return queryset


def _vendor_payments(organization, start=None, end=None):
    queryset = VendorPayment.objects.filter(organization=organization)
    if start and end:
        queryset = queryset.filter(payment_date__range=(start, end))
    return queryset


def _monthly_totals(queryset, start, end):
    rows = (
        queryset.filter(payment_date__range=(start, end))
        .annotate(month=TruncMonth("payment_date"))
        .values("month")
        .annotate(total=Coalesce(Sum("amount"), ZERO))
    )
    totals = {}
    for row in rows:
        if row["month"]:
            totals[(row["month"].year, row["month"].month)] = row["total"] or ZERO
    return totals


def build_overview(organization, query_params):
    context = resolve_period(organization, {"period": "this_fiscal_year"})
    start, end = context["start"], context["end"]

    incoming = _sum(_customer_payments(organization, start, end))
    outgoing = _sum(_vendor_payments(organization, start, end))
    receivables = _sum(Customer.objects.filter(organization=organization), "opening_balance")
    payables = _sum(Vendor.objects.filter(organization=organization), "opening_balance")

    all_incoming = _customer_payments(organization)
    bank_balance = _sum(all_incoming.exclude(bank_account_id=None))
    cash_in_hand = _sum(all_incoming.filter(bank_account_id=None))

    return {
        **dashboard_header(context, "overview"),
        "start_date": context["start_date"],
        "end_date": context["end_date"],
        "currency": context["currency"],
        "receivables": money(receivables),
        "payables": money(payables),
        "overdue_invoices_count": 0,
        "overdue_bills_count": 0,
        "bank_balance": money(bank_balance),
        "cash_in_hand": money(cash_in_hand),
        "income_total": money(incoming),
        "expense_total": money(outgoing),
        "quick_actions": QUICK_ACTIONS,
    }


def build_cash_flow(organization, query_params):
    context = resolve_period(organization, query_params)
    start, end = context["start"], context["end"]
    months = month_points_for_range(start, end)

    incoming_by_month = _monthly_totals(
        CustomerPayment.objects.filter(organization=organization),
        start,
        end,
    )
    outgoing_by_month = _monthly_totals(
        VendorPayment.objects.filter(organization=organization),
        start,
        end,
    )

    running = _sum(
        CustomerPayment.objects.filter(
            organization=organization,
            payment_date__lt=start,
        )
    ) - _sum(
        VendorPayment.objects.filter(
            organization=organization,
            payment_date__lt=start,
        )
    )
    series = []
    period_incoming = ZERO
    period_outgoing = ZERO

    for point in months:
        incoming = incoming_by_month.get((point["year"], point["month"]), ZERO)
        outgoing = outgoing_by_month.get((point["year"], point["month"]), ZERO)
        opening = running
        ending = opening + incoming - outgoing
        running = ending
        period_incoming += incoming
        period_outgoing += outgoing
        series.append(
            {
                "month": point["month_label"],
                "month_number": point["month"],
                "year": point["year"],
                "opening_balance": money(opening),
                "income": money(incoming),
                "outgoing": money(outgoing),
                "ending_balance": money(ending),
            }
        )

    opening_cash = Decimal(series[0]["opening_balance"]) if series else ZERO
    ending_cash = Decimal(series[-1]["ending_balance"]) if series else ZERO

    return {
        "title": "Cash Flow",
        "period": context["period"],
        "period_label": context["period_label"],
        "available_periods": available_periods(),
        "currency": context["currency"],
        "as_on_date": context["start_date"],
        "as_on_label": f"Cash as on {start.strftime('%d %b %Y')}",
        "opening_cash_balance": money(opening_cash),
        "incoming": money(period_incoming),
        "outgoing": money(period_outgoing),
        "ending_balance": money(ending_cash),
        "months": series,
    }


def build_income_expense(organization, query_params):
    context = resolve_period(organization, query_params)
    method = context["accounting_method"]
    if method not in ("accrual", "cash"):
        method = "accrual"

    start, end = context["start"], context["end"]
    months = month_points_for_range(start, end)
    income_by_month = _monthly_totals(
        CustomerPayment.objects.filter(organization=organization),
        start,
        end,
    )
    expense_by_month = _monthly_totals(
        VendorPayment.objects.filter(organization=organization),
        start,
        end,
    )

    series = []
    income_total = ZERO
    expense_total = ZERO
    for point in months:
        income = income_by_month.get((point["year"], point["month"]), ZERO)
        expense = expense_by_month.get((point["year"], point["month"]), ZERO)
        income_total += income
        expense_total += expense
        series.append(
            {
                "month": point["month_label"],
                "month_number": point["month"],
                "year": point["year"],
                "income": money(income),
                "expense": money(expense),
            }
        )

    return {
        "title": "Income and Expense",
        "period": context["period"],
        "period_label": context["period_label"],
        "available_periods": available_periods(),
        "accounting_method": method,
        "currency": context["currency"],
        "income_total": money(income_total),
        "expense_total": money(expense_total),
        "months": series,
    }


def build_projects(organization, query_params):
    context = resolve_period(organization, {"period": "this_fiscal_year"})
    return {
        "title": "Project Summary",
        "currency": context["currency"],
        "timer": "00:00:00",
        "associated_project": None,
        "unbilled_hours": "00:00",
        "unbilled_expenses": money(0),
        "actions": ["log_time", "start_timer"],
    }


def build_expense_breakdown(organization, query_params):
    context = resolve_period(organization, query_params)
    start, end = context["start"], context["end"]
    rows = (
        _vendor_payments(organization, start, end)
        .values("vendor__display_name")
        .annotate(total=Coalesce(Sum("amount"), ZERO))
        .order_by("-total")
    )

    categories = []
    total = ZERO
    for index, row in enumerate(rows):
        amount = row["total"] or ZERO
        total += amount
        categories.append(
            {
                "label": row["vendor__display_name"] or "Other",
                "amount": amount,
                "color": EXPENSE_COLORS[index % len(EXPENSE_COLORS)],
            }
        )

    if not categories:
        categories = [
            {"label": "Salaries & Wages", "amount": ZERO, "color": EXPENSE_COLORS[0]},
            {"label": "Rent & Utilities", "amount": ZERO, "color": EXPENSE_COLORS[1]},
            {"label": "Marketing", "amount": ZERO, "color": EXPENSE_COLORS[2]},
            {"label": "Supplies", "amount": ZERO, "color": EXPENSE_COLORS[3]},
            {"label": "Insurance", "amount": ZERO, "color": EXPENSE_COLORS[4]},
            {"label": "Other", "amount": ZERO, "color": EXPENSE_COLORS[5]},
        ]

    payload = []
    for category in categories:
        percent = Decimal("0.00")
        if total > 0:
            percent = (category["amount"] * Decimal("100") / total).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        payload.append(
            {
                "label": category["label"],
                "amount": money(category["amount"]),
                "percentage": f"{percent:.2f}",
                "color": category["color"],
            }
        )

    return {
        "title": "Expense Breakdown",
        "period": context["period"],
        "period_label": context["period_label"],
        "available_periods": available_periods(),
        "currency": context["currency"],
        "total_expense": money(total),
        "categories": payload,
    }


def build_updates(organization, query_params):
    context = resolve_period(organization, {"period": "this_fiscal_year"})
    now = timezone.now()
    updates = []
    unread_count = 0
    for item in UPDATE_ITEMS:
        published_at = now - item["age"]
        is_read = item["is_read"]
        if not is_read:
            unread_count += 1
        updates.append(
            {
                "key": item["key"],
                "type": item["type"],
                "icon": item["icon"],
                "title": item["title"],
                "description": item["description"],
                "published_at": published_at.isoformat(),
                "relative_time": relative_time(published_at, now),
                "is_read": is_read,
            }
        )

    return {
        **dashboard_header(context, "updates"),
        "unread_count": unread_count,
        "updates": updates,
    }


def build_support(organization, query_params):
    context = resolve_period(organization, {"period": "this_fiscal_year"})
    return {
        **dashboard_header(context, "support"),
        "heading": "How can we help you?",
        "subheading": "Find answers to common questions or contact support",
        "categories": SUPPORT_CATEGORIES,
        "contact": SUPPORT_CONTACT,
    }
