from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from apps.expenses.models import Expense
from apps.reports.financial import (
    DATE_RANGE_CHOICES,
    ZERO,
    format_report_date,
    money,
    money_display,
    money_text,
    organization_payload,
    resolve_date_range,
)

EXPENSE_REPORTS = (
    {
        "key": "expenses_by_category",
        "label": "Expenses by Category",
        "path": "/api/reports/expenses/expenses-by-category/",
        "form_path": "/api/reports/expenses/expenses-by-category/form/",
        "export_path": "/api/reports/expenses/expenses-by-category/export/",
    },
)

EMPTY_EXPENSES_MESSAGE = "No expenses during the selected date range."


def currency_amount(symbol, value):
    return f"{symbol}{money_display(value)}"


def expenses_date_form_payload(title, export_form_path):
    start, end = resolve_date_range("this_month")
    return {
        "title": title,
        "fields": {
            "date_range": {
                "label": "Date Range",
                "required": True,
                "choices": list(DATE_RANGE_CHOICES),
                "default": "this_month",
            },
            "date_from": {
                "label": "From",
                "required": False,
                "default": start.isoformat(),
                "display": format_report_date(start),
            },
            "date_to": {
                "label": "To",
                "required": False,
                "default": end.isoformat(),
                "display": format_report_date(end),
            },
        },
        "actions": {"run": "Run Report"},
        "export_form_path": export_form_path,
    }


def expenses_by_category_form_payload():
    return expenses_date_form_payload(
        "Expenses by Category",
        "/api/reports/expenses/expenses-by-category/export-form/",
    )


def build_expenses_by_category_report(organization, filters):
    country = getattr(organization, "country", None) or "IN"
    date_range = (filters.get("date_range") or "this_month").strip().lower()
    start, end = resolve_date_range(
        date_range,
        filters.get("date_from"),
        filters.get("date_to"),
        country=country,
    )
    symbol = organization_payload(organization)["currency_symbol"]
    grouped = (
        Expense.objects.filter(
            organization=organization,
            expense_date__range=(start, end),
        )
        .values("category_id", "category__name")
        .annotate(amount=Coalesce(Sum("amount"), ZERO), expense_count=Count("id"))
        .order_by("category__name")
    )

    rows = []
    total_amount = ZERO
    for item in grouped:
        amount = money(item["amount"])
        if amount == ZERO and not item["expense_count"]:
            continue
        total_amount += amount
        name = (item["category__name"] or "").strip() or "Uncategorized"
        rows.append(
            {
                "category_id": str(item["category_id"]) if item["category_id"] else None,
                "category": name,
                "category_display": name,
                "amount": money_text(amount),
                "amount_display": currency_amount(symbol, amount),
                "expense_count": item["expense_count"],
                "label": name,
                "is_total": False,
            }
        )

    payload = organization_payload(organization)
    payload.update(
        {
            "key": "expenses_by_category",
            "title": "Expenses by Category",
            "section": "expenses",
            "section_label": "Expenses",
            "date_range": date_range,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "date_from_display": format_report_date(start),
            "date_to_display": format_report_date(end),
            "period_display": f"From {format_report_date(start)} To {format_report_date(end)}",
            "basis_label": "Basis: Cash",
            "columns": [
                {"key": "category", "label": "CATEGORY"},
                {"key": "amount", "label": "AMOUNT"},
            ],
            "rows": rows,
            "empty": len(rows) == 0,
            "empty_message": EMPTY_EXPENSES_MESSAGE if not rows else "",
            "totals": {
                "label": "Total",
                "amount": money_text(total_amount),
                "amount_display": currency_amount(symbol, total_amount),
            },
        }
    )
    if rows:
        rows.append(
            {
                "category_id": None,
                "category": "Total",
                "category_display": "Total",
                "amount": money_text(total_amount),
                "amount_display": currency_amount(symbol, total_amount),
                "expense_count": None,
                "label": "Total",
                "is_total": True,
            }
        )
    return payload
