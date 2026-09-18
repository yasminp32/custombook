from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from apps.banking.models import BankAccount
from apps.bills.models import Bill
from apps.credit_notes.models import CreditNote
from apps.dashboard.periods import fiscal_year_bounds, fiscal_year_start_month
from apps.expenses.models import Expense
from apps.inventory.models import InventoryAdjustment
from apps.invoices.models import Invoice
from apps.items.models import Item
from apps.payments_made.models import PaymentMade
from apps.payments_received.models import PaymentReceived
from apps.vendor_credits.models import VendorCredit

ZERO = Decimal("0.00")
MONEY = Decimal("0.01")

ACTIVE_INVOICE = ~Q(status__in=(Invoice.Status.DRAFT, Invoice.Status.CANCELLED))
ACTIVE_BILL = ~Q(status=Bill.Status.DRAFT)
ACTIVE_CREDIT = ~Q(status__in=(CreditNote.Status.DRAFT, CreditNote.Status.VOID))
ACTIVE_VENDOR_CREDIT = ~Q(
    status__in=(VendorCredit.Status.DRAFT, VendorCredit.Status.VOID)
)

AS_OF_DATE_CHOICES = (
    {"value": "today", "label": "Today"},
    {"value": "end_of_this_week", "label": "End of this Week"},
    {"value": "end_of_this_month", "label": "End of this Month"},
    {"value": "end_of_previous_month", "label": "End of Previous Month"},
    {"value": "end_of_this_quarter", "label": "End of this Quarter"},
    {"value": "end_of_this_year", "label": "End of this Year"},
)

DATE_RANGE_CHOICES = (
    {"value": "today", "label": "Today"},
    {"value": "this_week", "label": "This Week"},
    {"value": "this_month", "label": "This Month"},
    {"value": "this_quarter", "label": "This Quarter"},
    {"value": "this_year", "label": "This Year"},
    {"value": "previous_week", "label": "Previous Week"},
    {"value": "previous_month", "label": "Previous Month"},
    {"value": "previous_quarter", "label": "Previous Quarter"},
    {"value": "previous_year", "label": "Previous Year"},
    {"value": "custom", "label": "Custom"},
)

REPORT_BASIS_CHOICES = (
    {"value": "cash", "label": "Cash"},
    {"value": "accrual", "label": "Accrual"},
)

FILTER_ACCOUNTS_CHOICES = (
    {
        "value": "without_zero_balance",
        "label": "Accounts Without Zero Balance",
    },
    {"value": "all_accounts", "label": "All Accounts"},
)

COMPARE_WITH_CHOICES = (
    {"value": "none", "label": "None"},
    {"value": "previous_period", "label": "Previous Period"},
    {"value": "previous_year", "label": "Previous Year"},
)

TABLE_DENSITY_CHOICES = (
    {"value": "classic", "label": "Classic"},
    {"value": "compact", "label": "Compact"},
    {"value": "comfortable", "label": "Comfortable"},
)

PAPER_SIZE_CHOICES = (
    {"value": "A4", "label": "A4"},
    {"value": "letter", "label": "Letter"},
    {"value": "legal", "label": "Legal"},
)

ORIENTATION_CHOICES = (
    {"value": "portrait", "label": "Portrait"},
    {"value": "landscape", "label": "Landscape"},
)

LANGUAGE_CHOICES = (
    {"value": "en", "label": "English"},
    {"value": "ar", "label": "Arabic"},
)

FINANCIAL_REPORTS = (
    {
        "key": "balance_sheet",
        "label": "Balance Sheet",
        "path": "/api/reports/financial/balance-sheet/",
        "form_path": "/api/reports/financial/balance-sheet/form/",
        "export_path": "/api/reports/financial/balance-sheet/export/",
    },
    {
        "key": "profit_and_loss",
        "label": "Profit and Loss",
        "path": "/api/reports/financial/profit-and-loss/",
        "form_path": "/api/reports/financial/profit-and-loss/form/",
        "export_path": "/api/reports/financial/profit-and-loss/export/",
    },
    {
        "key": "cash_flow_statement",
        "label": "Cash Flow Statement",
        "path": "/api/reports/financial/cash-flow-statement/",
        "form_path": "/api/reports/financial/cash-flow-statement/form/",
        "export_path": "/api/reports/financial/cash-flow-statement/export/",
    },
)

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AED": "د.إ"}


def money(value):
    amount = Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)
    return amount


def money_text(value):
    return f"{money(value):.2f}"


def money_display(value):
    return f"{money(value):,.2f}"


def is_zero(value):
    return money(value) == ZERO


def format_report_date(value):
    return f"{value.day} {value.strftime('%b %Y')}"


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        year, month, day = text[:10].split("-")
        return date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None


def quarter_end(value):
    quarter = ((value.month - 1) // 3) + 1
    month = quarter * 3
    return date(value.year, month, monthrange(value.year, month)[1])


def add_months(value, months):
    month_index = value.year * 12 + (value.month - 1) + months
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def last_day_of_month(year, month):
    return date(year, month, monthrange(year, month)[1])


def resolve_as_of_date(as_of_date="today", report_date=None, today=None):
    explicit = parse_date(report_date)
    if explicit:
        return explicit
    today = today or date.today()
    key = (as_of_date or "today").strip().lower()
    if key == "end_of_this_week":
        return today + timedelta(days=(6 - today.weekday()))
    if key == "end_of_this_month":
        return last_day_of_month(today.year, today.month)
    if key == "end_of_previous_month":
        first = today.replace(day=1)
        return first - timedelta(days=1)
    if key == "end_of_this_quarter":
        return quarter_end(today)
    if key == "end_of_this_year":
        return date(today.year, 12, 31)
    return today


def previous_period_as_of(as_of, as_of_date="today"):
    key = (as_of_date or "today").strip().lower()
    if key == "end_of_this_week":
        return as_of - timedelta(days=7)
    if key in ("end_of_this_month", "end_of_previous_month"):
        return as_of.replace(day=1) - timedelta(days=1)
    if key == "end_of_this_quarter":
        return quarter_end(add_months(as_of.replace(day=1), -3))
    if key == "end_of_this_year":
        return date(as_of.year - 1, 12, 31)
    return as_of - timedelta(days=1)


def previous_year_date(value):
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return date(value.year - 1, 2, 28)


def resolve_compare_date(as_of, as_of_date, compare_with):
    key = (compare_with or "none").strip().lower()
    if key == "previous_period":
        return previous_period_as_of(as_of, as_of_date)
    if key == "previous_year":
        return previous_year_date(as_of)
    return None


def resolve_date_range(date_range="this_month", date_from=None, date_to=None, today=None, country="IN"):
    today = today or date.today()
    key = (date_range or "this_month").strip().lower()
    start = parse_date(date_from)
    end = parse_date(date_to)
    if key == "custom" or (not date_range and start and end):
        if start and end:
            if start > end:
                start, end = end, start
            return start, end
        key = "this_month"
    if key == "today":
        return today, today
    if key == "this_week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end
    if key == "this_month":
        return today.replace(day=1), last_day_of_month(today.year, today.month)
    if key == "this_quarter":
        quarter = ((today.month - 1) // 3) + 1
        start_month = (quarter - 1) * 3 + 1
        start = date(today.year, start_month, 1)
        return start, quarter_end(today)
    if key == "this_year":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if key == "previous_week":
        this_week_start = today - timedelta(days=today.weekday())
        end = this_week_start - timedelta(days=1)
        start = end - timedelta(days=6)
        return start, end
    if key == "previous_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if key == "previous_quarter":
        current_start_month = ((today.month - 1) // 3) * 3 + 1
        current_start = date(today.year, current_start_month, 1)
        end = current_start - timedelta(days=1)
        start_month = ((end.month - 1) // 3) * 3 + 1
        return date(end.year, start_month, 1), end
    if key == "previous_year":
        year = today.year - 1
        return date(year, 1, 1), date(year, 12, 31)
    start_month = fiscal_year_start_month(country)
    if key == "previous_fiscal_year":
        current_start, _ = fiscal_year_bounds(today, start_month)
        previous_today = date(current_start.year - 1, current_start.month, 1)
        return fiscal_year_bounds(previous_today, start_month)
    if key == "this_fiscal_year":
        return fiscal_year_bounds(today, start_month)
    return today.replace(day=1), last_day_of_month(today.year, today.month)


def previous_range(start, end, compare_with):
    key = (compare_with or "none").strip().lower()
    if key == "previous_period":
        length = (end - start).days + 1
        compare_end = start - timedelta(days=1)
        compare_start = compare_end - timedelta(days=length - 1)
        return compare_start, compare_end
    if key == "previous_year":
        return previous_year_date(start), previous_year_date(end)
    return None, None


def _sum(queryset, field="amount"):
    total = queryset.aggregate(total=Coalesce(Sum(field), ZERO))["total"]
    return Decimal(total or 0)


def account_balance_as_of(account, as_of):
    transactions = account.transactions.all()
    all_signed = ZERO
    as_of_signed = ZERO
    has_transactions = False
    for row in transactions:
        has_transactions = True
        signed = Decimal(row.signed_amount or 0)
        all_signed += signed
        if row.transaction_date <= as_of:
            as_of_signed += signed
    current = Decimal(account.books_balance or 0)
    if has_transactions:
        opening = current - all_signed
        return opening + as_of_signed
    return current


def inventory_value_as_of(organization, as_of):
    items = Item.objects.filter(organization=organization, track_inventory=True)
    total = ZERO
    for item in items:
        stock = Decimal(item.opening_stock or 0)
        rate = Decimal(item.rate_per_unit or 0)
        total += stock * rate
    adjustments = InventoryAdjustment.objects.filter(
        organization=organization,
        status=InventoryAdjustment.Status.COMPLETED,
        date__lte=as_of,
    )
    total += _sum(adjustments, "adjustment_value")
    return total


def cash_sales_as_of(organization, as_of):
    return _sum(
        PaymentReceived.objects.filter(
            organization=organization,
            payment_date__lte=as_of,
            payment_mode=PaymentReceived.PaymentMode.CASH,
            bank_account_id__isnull=True,
        )
    )


def receivables_as_of(organization, as_of):
    invoices = Invoice.objects.filter(
        organization=organization,
        invoice_date__lte=as_of,
    ).filter(ACTIVE_INVOICE)
    total = ZERO
    for row in invoices:
        due = Decimal(row.total_amount or 0) - Decimal(row.amount_paid or 0)
        if due > 0:
            total += due
    credits = _sum(
        CreditNote.objects.filter(
            organization=organization,
            credit_note_date__lte=as_of,
        ).filter(ACTIVE_CREDIT)
    )
    remaining = total - credits
    return remaining if remaining > 0 else ZERO


def payables_as_of(organization, as_of):
    bills = Bill.objects.filter(
        organization=organization,
        bill_date__lte=as_of,
    ).filter(ACTIVE_BILL)
    total = ZERO
    for row in bills:
        due = Decimal(row.amount or 0) - Decimal(row.amount_paid or 0)
        if due > 0:
            total += due
    credits = _sum(
        VendorCredit.objects.filter(
            organization=organization,
            credit_date__lte=as_of,
        ).filter(ACTIVE_VENDOR_CREDIT)
    )
    remaining = total - credits
    return remaining if remaining > 0 else ZERO


def net_income(organization, start, end, basis):
    if basis == "cash":
        income = _sum(
            PaymentReceived.objects.filter(
                organization=organization,
                payment_date__range=(start, end),
            )
        )
        expenses = _sum(
            PaymentMade.objects.filter(
                organization=organization,
                payment_date__range=(start, end),
            )
        ) + _sum(
            Expense.objects.filter(
                organization=organization,
                expense_date__range=(start, end),
            )
        )
        return income - expenses
    income = _sum(
        Invoice.objects.filter(
            organization=organization,
            invoice_date__range=(start, end),
        ).filter(ACTIVE_INVOICE),
        "total_amount",
    ) - _sum(
        CreditNote.objects.filter(
            organization=organization,
            credit_note_date__range=(start, end),
        ).filter(ACTIVE_CREDIT)
    )
    expenses = _sum(
        Expense.objects.filter(
            organization=organization,
            expense_date__range=(start, end),
        )
    ) + _sum(
        Bill.objects.filter(
            organization=organization,
            bill_date__range=(start, end),
        ).filter(ACTIVE_BILL)
    ) - _sum(
        VendorCredit.objects.filter(
            organization=organization,
            credit_date__range=(start, end),
        ).filter(ACTIVE_VENDOR_CREDIT)
    )
    return income - expenses


def expense_rows(organization, start, end):
    rows = []
    expenses = (
        Expense.objects.filter(
            organization=organization,
            expense_date__range=(start, end),
        )
        .values("category__name")
        .annotate(total=Coalesce(Sum("amount"), ZERO))
        .order_by("category__name")
    )
    for row in expenses:
        label = row["category__name"] or "Uncategorized"
        rows.append((label, Decimal(row["total"] or 0)))
    return rows


def make_node(key, label, row_type, amount=ZERO, compare_amount=None, children=None, account_id=None):
    children = children or []
    if children:
        amount = sum(
            (child["amount_value"] for child in children if child["row_type"] != "total"),
            ZERO,
        )
        if compare_amount is not None or any(
            child.get("compare_amount_value") is not None for child in children
        ):
            compare_amount = sum(
                (
                    child.get("compare_amount_value") or ZERO
                    for child in children
                    if child["row_type"] != "total"
                ),
                ZERO,
            )
    return {
        "key": key,
        "label": label,
        "row_type": row_type,
        "account_id": str(account_id) if account_id else None,
        "amount_value": money(amount),
        "amount": money_text(amount),
        "amount_display": money_display(amount),
        "compare_amount_value": None if compare_amount is None else money(compare_amount),
        "compare_amount": None if compare_amount is None else money_text(compare_amount),
        "compare_amount_display": None
        if compare_amount is None
        else money_display(compare_amount),
        "children": children,
    }


def total_node(label, amount, compare_amount=None):
    node = make_node(
        f"total_{label.lower().replace(' ', '_')}",
        label,
        "total",
        amount,
        compare_amount,
    )
    return node


def filter_zero_nodes(nodes, include_zero):
    if include_zero:
        return nodes
    filtered = []
    for node in nodes:
        children = filter_zero_nodes(node.get("children") or [], include_zero)
        node = dict(node)
        node["children"] = children
        if node["row_type"] == "account" and is_zero(node["amount_value"]):
            compare = node.get("compare_amount_value")
            if compare is None or is_zero(compare):
                continue
        filtered.append(node)
    return filtered


def flatten_nodes(nodes, depth=0):
    rows = []
    for node in nodes:
        rows.append(
            {
                "key": node["key"],
                "label": node["label"],
                "row_type": node["row_type"],
                "account_id": node.get("account_id"),
                "depth": depth,
                "amount": node["amount"],
                "amount_display": node["amount_display"],
                "compare_amount": node.get("compare_amount"),
                "compare_amount_display": node.get("compare_amount_display"),
            }
        )
        rows.extend(flatten_nodes(node.get("children") or [], depth + 1))
    return rows


def strip_internal(nodes):
    cleaned = []
    for node in nodes:
        cleaned.append(
            {
                "key": node["key"],
                "label": node["label"],
                "row_type": node["row_type"],
                "account_id": node.get("account_id"),
                "amount": node["amount"],
                "amount_display": node["amount_display"],
                "compare_amount": node.get("compare_amount"),
                "compare_amount_display": node.get("compare_amount_display"),
                "children": strip_internal(node.get("children") or []),
            }
        )
    return cleaned


def bank_groups(organization, as_of, compare_as_of):
    accounts = list(
        BankAccount.objects.filter(organization=organization).order_by("name")
    )
    cash_children = []
    bank_children = []
    card_children = []
    for account in accounts:
        current = account_balance_as_of(account, as_of)
        compare = (
            account_balance_as_of(account, compare_as_of)
            if compare_as_of
            else None
        )
        node = make_node(
            f"account_{account.id}",
            account.name,
            "account",
            current,
            compare,
            account_id=account.id,
        )
        if account.account_type in (
            BankAccount.AccountType.CASH,
            BankAccount.AccountType.UNDEPOSITED_FUNDS,
        ):
            cash_children.append(node)
        elif account.account_type == BankAccount.AccountType.CREDIT_CARD:
            card_children.append(node)
        else:
            bank_children.append(node)
    return cash_children, bank_children, card_children


def ytd_bounds(organization, as_of):
    country = getattr(organization, "country", None) or "IN"
    start, _ = fiscal_year_bounds(as_of, fiscal_year_start_month(country))
    if start > as_of:
        start = date(as_of.year, 1, 1)
    return start, as_of


def build_balance_sheet_tree(organization, as_of, basis, compare_as_of):
    cash_children, bank_children, card_children = bank_groups(
        organization, as_of, compare_as_of
    )
    ar = ZERO if basis == "cash" else receivables_as_of(organization, as_of)
    ar_compare = None
    if compare_as_of:
        ar_compare = ZERO if basis == "cash" else receivables_as_of(
            organization, compare_as_of
        )
    inventory = inventory_value_as_of(organization, as_of)
    inventory_compare = (
        inventory_value_as_of(organization, compare_as_of) if compare_as_of else None
    )
    cash_sales = cash_sales_as_of(organization, as_of)
    cash_sales_compare = (
        cash_sales_as_of(organization, compare_as_of) if compare_as_of else None
    )
    ap = ZERO if basis == "cash" else payables_as_of(organization, as_of)
    ap_compare = None
    if compare_as_of:
        ap_compare = ZERO if basis == "cash" else payables_as_of(
            organization, compare_as_of
        )

    ytd_start, ytd_end = ytd_bounds(organization, as_of)
    earnings = net_income(organization, ytd_start, ytd_end, basis)
    earnings_compare = None
    if compare_as_of:
        compare_start, compare_end = ytd_bounds(organization, compare_as_of)
        earnings_compare = net_income(
            organization, compare_start, compare_end, basis
        )

    cash_group = make_node(
        "cash",
        "Cash",
        "group",
        children=cash_children
        + [total_node("Total for Cash", ZERO, ZERO if compare_as_of else None)],
    )
    if cash_group["children"]:
        cash_group["children"][-1] = total_node(
            "Total for Cash",
            cash_group["amount_value"],
            cash_group["compare_amount_value"],
        )
    bank_group = make_node(
        "bank",
        "Bank",
        "group",
        children=bank_children
        + [total_node("Total for Bank", ZERO, ZERO if compare_as_of else None)],
    )
    if bank_group["children"]:
        bank_group["children"][-1] = total_node(
            "Total for Bank",
            bank_group["amount_value"],
            bank_group["compare_amount_value"],
        )
    cash_equivalents = make_node(
        "cash_and_cash_equivalents",
        "Cash and Cash Equivalents",
        "group",
        children=[
            cash_group,
            bank_group,
            total_node(
                "Total for Cash and Cash Equivalents",
                ZERO,
                ZERO if compare_as_of else None,
            ),
        ],
    )
    cash_equivalents["children"][-1] = total_node(
        "Total for Cash and Cash Equivalents",
        cash_equivalents["amount_value"],
        cash_equivalents["compare_amount_value"],
    )

    other_current = make_node(
        "other_current_assets",
        "Other current assets",
        "group",
        children=[
            make_node(
                "inventory_asset",
                "Inventory Asset",
                "account",
                inventory,
                inventory_compare,
            ),
            make_node(
                "sales_to_customers_cash",
                "Sales to Customers (Cash)",
                "account",
                cash_sales,
                cash_sales_compare,
            ),
            total_node(
                "Total for Other current assets",
                ZERO,
                ZERO if compare_as_of else None,
            ),
        ],
    )
    other_current["children"][-1] = total_node(
        "Total for Other current assets",
        other_current["amount_value"],
        other_current["compare_amount_value"],
    )

    ar_group = make_node(
        "accounts_receivable",
        "Accounts Receivable",
        "group",
        children=[
            make_node(
                "accounts_receivable_balance",
                "Accounts Receivable",
                "account",
                ar,
                ar_compare,
            ),
            total_node(
                "Total for Accounts Receivable",
                ar,
                ar_compare,
            ),
        ],
    )
    ar_group["children"][-1] = total_node(
        "Total for Accounts Receivable",
        ar_group["amount_value"],
        ar_group["compare_amount_value"],
    )

    current_assets = make_node(
        "current_assets",
        "Current Assets",
        "group",
        children=[
            cash_equivalents,
            ar_group,
            other_current,
            total_node(
                "Total for Current Assets",
                ZERO,
                ZERO if compare_as_of else None,
            ),
        ],
    )
    current_assets["children"][-1] = total_node(
        "Total for Current Assets",
        current_assets["amount_value"],
        current_assets["compare_amount_value"],
    )
    non_current = make_node(
        "non_current_assets",
        "Non Current Assets",
        "group",
        children=[
            total_node(
                "Total for Non Current Assets",
                ZERO,
                ZERO if compare_as_of else None,
            )
        ],
    )
    fixed_assets = make_node(
        "fixed_assets",
        "Fixed Assets",
        "group",
        children=[
            total_node(
                "Total for Fixed Assets",
                ZERO,
                ZERO if compare_as_of else None,
            )
        ],
    )
    assets = make_node(
        "assets",
        "Assets",
        "section",
        children=[
            current_assets,
            non_current,
            fixed_assets,
            total_node("Total for Assets", ZERO, ZERO if compare_as_of else None),
        ],
    )
    assets["children"][-1] = total_node(
        "Total for Assets",
        assets["amount_value"],
        assets["compare_amount_value"],
    )

    ap_group = make_node(
        "accounts_payable",
        "Accounts Payable",
        "group",
        children=[
            make_node(
                "accounts_payable_balance",
                "Accounts Payable",
                "account",
                ap,
                ap_compare,
            ),
            total_node("Total for Accounts Payable", ap, ap_compare),
        ],
    )
    credit_cards = make_node(
        "credit_cards",
        "Credit Card",
        "group",
        children=card_children
        + [total_node("Total for Credit Card", ZERO, ZERO if compare_as_of else None)],
    )
    if credit_cards["children"]:
        credit_cards["children"][-1] = total_node(
            "Total for Credit Card",
            credit_cards["amount_value"],
            credit_cards["compare_amount_value"],
        )
    current_liabilities = make_node(
        "current_liabilities",
        "Current Liabilities",
        "group",
        children=[
            ap_group,
            credit_cards,
            total_node(
                "Total for Current Liabilities",
                ZERO,
                ZERO if compare_as_of else None,
            ),
        ],
    )
    current_liabilities["children"][-1] = total_node(
        "Total for Current Liabilities",
        current_liabilities["amount_value"],
        current_liabilities["compare_amount_value"],
    )
    liabilities = make_node(
        "liabilities",
        "Liabilities",
        "section",
        children=[
            current_liabilities,
            total_node(
                "Total for Liabilities",
                ZERO,
                ZERO if compare_as_of else None,
            ),
        ],
    )
    liabilities["children"][-1] = total_node(
        "Total for Liabilities",
        liabilities["amount_value"],
        liabilities["compare_amount_value"],
    )

    residual = assets["amount_value"] - liabilities["amount_value"] - earnings
    residual_compare = None
    if compare_as_of is not None:
        residual_compare = (
            (assets["compare_amount_value"] or ZERO)
            - (liabilities["compare_amount_value"] or ZERO)
            - (earnings_compare or ZERO)
        )
    equity = make_node(
        "equity",
        "Equity",
        "section",
        children=[
            make_node(
                "opening_balance_equity",
                "Opening Balance Equity",
                "account",
                residual,
                residual_compare,
            ),
            make_node(
                "current_year_earnings",
                "Current Year Earnings",
                "account",
                earnings,
                earnings_compare,
            ),
            total_node("Total for Equity", ZERO, ZERO if compare_as_of else None),
        ],
    )
    equity["children"][-1] = total_node(
        "Total for Equity",
        equity["amount_value"],
        equity["compare_amount_value"],
    )
    return [assets, liabilities, equity]


def report_columns(as_of, compare_as_of):
    columns = [
        {"key": "account", "label": "ACCOUNT"},
        {"key": "total", "label": "TOTAL"},
    ]
    if compare_as_of:
        columns.append(
            {
                "key": "compare",
                "label": format_report_date(compare_as_of),
            }
        )
    return columns


def organization_payload(organization):
    currency = organization.currency or "INR"
    return {
        "organization_id": str(organization.id),
        "organization_name": organization.name,
        "organization_details": {
            "country": organization.country,
            "state": organization.state,
            "currency": currency,
        },
        "currency": currency,
        "currency_symbol": CURRENCY_SYMBOLS.get(currency, currency),
        "currency_note": "Amount is displayed in your base currency",
    }


def build_balance_sheet_report(organization, filters):
    as_of_key = (filters.get("as_of_date") or "today").strip().lower()
    as_of = resolve_as_of_date(as_of_key, filters.get("report_date"))
    basis = (filters.get("report_basis") or "cash").strip().lower()
    if basis not in ("cash", "accrual"):
        basis = "cash"
    filter_accounts = (
        filters.get("filter_accounts") or "without_zero_balance"
    ).strip().lower()
    compare_with = (filters.get("compare_with") or "none").strip().lower()
    compare_as_of = resolve_compare_date(as_of, as_of_key, compare_with)
    include_zero = filter_accounts == "all_accounts"
    sections = build_balance_sheet_tree(organization, as_of, basis, compare_as_of)
    sections = filter_zero_nodes(sections, include_zero)
    payload = organization_payload(organization)
    payload.update(
        {
            "key": "balance_sheet",
            "title": "Balance Sheet",
            "basis": basis,
            "basis_label": f"Basis : {'Cash' if basis == 'cash' else 'Accrual'}",
            "as_of": as_of.isoformat(),
            "as_of_date": as_of_key,
            "report_date": format_report_date(as_of),
            "as_of_display": f"As of {format_report_date(as_of)}",
            "filter_accounts": filter_accounts,
            "compare_with": compare_with,
            "compare_as_of": compare_as_of.isoformat() if compare_as_of else None,
            "columns": report_columns(as_of, compare_as_of),
            "sections": strip_internal(sections),
            "rows": flatten_nodes(sections),
            "totals": {
                "assets": next(
                    (row["amount"] for row in flatten_nodes(sections) if row["key"] == "assets"),
                    money_text(ZERO),
                ),
                "liabilities": next(
                    (
                        row["amount"]
                        for row in flatten_nodes(sections)
                        if row["key"] == "liabilities"
                    ),
                    money_text(ZERO),
                ),
                "equity": next(
                    (row["amount"] for row in flatten_nodes(sections) if row["key"] == "equity"),
                    money_text(ZERO),
                ),
            },
        }
    )
    return payload


def build_profit_and_loss_tree(organization, start, end, basis, compare_start, compare_end):
    if basis == "cash":
        operating_income = _sum(
            PaymentReceived.objects.filter(
                organization=organization,
                payment_date__range=(start, end),
            )
        )
        compare_income = (
            _sum(
                PaymentReceived.objects.filter(
                    organization=organization,
                    payment_date__range=(compare_start, compare_end),
                )
            )
            if compare_start
            else None
        )
        bills_amount = _sum(
            PaymentMade.objects.filter(
                organization=organization,
                payment_date__range=(start, end),
            )
        )
        compare_bills = (
            _sum(
                PaymentMade.objects.filter(
                    organization=organization,
                    payment_date__range=(compare_start, compare_end),
                )
            )
            if compare_start
            else None
        )
    else:
        operating_income = _sum(
            Invoice.objects.filter(
                organization=organization,
                invoice_date__range=(start, end),
            ).filter(ACTIVE_INVOICE),
            "total_amount",
        ) - _sum(
            CreditNote.objects.filter(
                organization=organization,
                credit_note_date__range=(start, end),
            ).filter(ACTIVE_CREDIT)
        )
        compare_income = None
        if compare_start:
            compare_income = _sum(
                Invoice.objects.filter(
                    organization=organization,
                    invoice_date__range=(compare_start, compare_end),
                ).filter(ACTIVE_INVOICE),
                "total_amount",
            ) - _sum(
                CreditNote.objects.filter(
                    organization=organization,
                    credit_note_date__range=(compare_start, compare_end),
                ).filter(ACTIVE_CREDIT)
            )
        bills_amount = _sum(
            Bill.objects.filter(
                organization=organization,
                bill_date__range=(start, end),
            ).filter(ACTIVE_BILL)
        ) - _sum(
            VendorCredit.objects.filter(
                organization=organization,
                credit_date__range=(start, end),
            ).filter(ACTIVE_VENDOR_CREDIT)
        )
        compare_bills = None
        if compare_start:
            compare_bills = _sum(
                Bill.objects.filter(
                    organization=organization,
                    bill_date__range=(compare_start, compare_end),
                ).filter(ACTIVE_BILL)
            ) - _sum(
                VendorCredit.objects.filter(
                    organization=organization,
                    credit_date__range=(compare_start, compare_end),
                ).filter(ACTIVE_VENDOR_CREDIT)
            )

    expense_map = {label: amount for label, amount in expense_rows(organization, start, end)}
    compare_expense_map = {}
    if compare_start:
        compare_expense_map = {
            label: amount
            for label, amount in expense_rows(organization, compare_start, compare_end)
        }
    expense_children = []
    labels = sorted(set(expense_map) | set(compare_expense_map))
    for label in labels:
        expense_children.append(
            make_node(
                f"expense_{label.lower().replace(' ', '_')}",
                label,
                "account",
                expense_map.get(label, ZERO),
                compare_expense_map.get(label) if compare_start else None,
            )
        )
    if bills_amount or (compare_bills and not is_zero(compare_bills)):
        expense_children.append(
            make_node(
                "purchases",
                "Purchases",
                "account",
                bills_amount,
                compare_bills,
            )
        )
    operating_income_node = make_node(
        "operating_income",
        "Operating Income",
        "group",
        children=[
            make_node(
                "sales",
                "Sales",
                "account",
                operating_income,
                compare_income,
            ),
            total_node(
                "Total for Operating Income",
                operating_income,
                compare_income,
            ),
        ],
    )
    cogs = make_node(
        "cost_of_goods_sold",
        "Cost of Goods Sold",
        "group",
        children=[
            total_node(
                "Total for Cost of Goods Sold",
                ZERO,
                ZERO if compare_start else None,
            )
        ],
    )
    gross_profit = operating_income_node["amount_value"] - cogs["amount_value"]
    gross_compare = None
    if compare_start:
        gross_compare = (operating_income_node["compare_amount_value"] or ZERO) - (
            cogs["compare_amount_value"] or ZERO
        )
    operating_expense = make_node(
        "operating_expense",
        "Operating Expense",
        "group",
        children=expense_children
        + [
            total_node(
                "Total for Operating Expense",
                ZERO,
                ZERO if compare_start else None,
            )
        ],
    )
    if operating_expense["children"]:
        operating_expense["children"][-1] = total_node(
            "Total for Operating Expense",
            operating_expense["amount_value"],
            operating_expense["compare_amount_value"],
        )
    operating_profit = gross_profit - operating_expense["amount_value"]
    operating_profit_compare = None
    if compare_start:
        operating_profit_compare = (gross_compare or ZERO) - (
            operating_expense["compare_amount_value"] or ZERO
        )
    non_operating_income = make_node(
        "non_operating_income",
        "Non Operating Income",
        "group",
        children=[
            total_node(
                "Total for Non Operating Income",
                ZERO,
                ZERO if compare_start else None,
            )
        ],
    )
    non_operating_expense = make_node(
        "non_operating_expense",
        "Non Operating Expense",
        "group",
        children=[
            total_node(
                "Total for Non Operating Expense",
                ZERO,
                ZERO if compare_start else None,
            )
        ],
    )
    net_profit = (
        operating_profit
        + non_operating_income["amount_value"]
        - non_operating_expense["amount_value"]
    )
    net_profit_compare = None
    if compare_start:
        net_profit_compare = (
            (operating_profit_compare or ZERO)
            + (non_operating_income["compare_amount_value"] or ZERO)
            - (non_operating_expense["compare_amount_value"] or ZERO)
        )
    return [
        operating_income_node,
        cogs,
        make_node("gross_profit", "Gross Profit", "total", gross_profit, gross_compare),
        operating_expense,
        make_node(
            "operating_profit",
            "Operating Profit",
            "total",
            operating_profit,
            operating_profit_compare,
        ),
        non_operating_income,
        non_operating_expense,
        make_node(
            "net_profit",
            "Net Profit/Loss",
            "total",
            net_profit,
            net_profit_compare,
        ),
    ]


def build_profit_and_loss_report(organization, filters):
    country = getattr(organization, "country", None) or "IN"
    date_range = (filters.get("date_range") or "this_month").strip().lower()
    start, end = resolve_date_range(
        date_range,
        filters.get("date_from"),
        filters.get("date_to"),
        country=country,
    )
    basis = (filters.get("report_basis") or "cash").strip().lower()
    if basis not in ("cash", "accrual"):
        basis = "cash"
    filter_accounts = (
        filters.get("filter_accounts") or "without_zero_balance"
    ).strip().lower()
    compare_with = (filters.get("compare_with") or "none").strip().lower()
    compare_start, compare_end = previous_range(start, end, compare_with)
    sections = build_profit_and_loss_tree(
        organization, start, end, basis, compare_start, compare_end
    )
    sections = filter_zero_nodes(sections, filter_accounts == "all_accounts")
    payload = organization_payload(organization)
    compare_as_of = compare_end
    payload.update(
        {
            "key": "profit_and_loss",
            "title": "Profit and Loss",
            "basis": basis,
            "basis_label": f"Basis : {'Cash' if basis == 'cash' else 'Accrual'}",
            "date_range": date_range,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "date_from_display": format_report_date(start),
            "date_to_display": format_report_date(end),
            "period_display": f"From {format_report_date(start)} To {format_report_date(end)}",
            "filter_accounts": filter_accounts,
            "compare_with": compare_with,
            "compare_date_from": compare_start.isoformat() if compare_start else None,
            "compare_date_to": compare_end.isoformat() if compare_end else None,
            "columns": report_columns(end, compare_as_of),
            "sections": strip_internal(sections),
            "rows": flatten_nodes(sections),
            "totals": {
                "net_profit": next(
                    (
                        row["amount"]
                        for row in flatten_nodes(sections)
                        if row["key"] == "net_profit"
                    ),
                    money_text(ZERO),
                )
            },
        }
    )
    return payload


def cash_at_date(organization, as_of):
    accounts = BankAccount.objects.filter(organization=organization).exclude(
        account_type=BankAccount.AccountType.CREDIT_CARD
    )
    total = ZERO
    for account in accounts:
        total += account_balance_as_of(account, as_of)
    return total


def build_cash_flow_tree(organization, start, end, basis, compare_start, compare_end):
    beginning = cash_at_date(organization, start - timedelta(days=1))
    ending = cash_at_date(organization, end)
    income = net_income(organization, start, end, basis)
    investing_amount = ZERO
    financing_amount = ZERO
    net_change = ending - beginning
    non_cash = net_change - income - investing_amount - financing_amount
    operating_amount = income + non_cash

    compare_beginning = compare_ending = compare_income = None
    compare_non_cash = compare_operating = compare_net_change = None
    compare_investing = compare_financing = None
    if compare_start:
        compare_beginning = cash_at_date(
            organization, compare_start - timedelta(days=1)
        )
        compare_ending = cash_at_date(organization, compare_end)
        compare_income = net_income(
            organization, compare_start, compare_end, basis
        )
        compare_net_change = compare_ending - compare_beginning
        compare_non_cash = (
            compare_net_change - compare_income - ZERO - ZERO
        )
        compare_operating = compare_income + compare_non_cash
        compare_investing = ZERO
        compare_financing = ZERO

    non_cash_group = make_node(
        "non_cash_adjustments",
        "Non-cash adjustments",
        "group",
        children=[
            make_node(
                "non_cash_adjustments_amount",
                "Non-cash adjustments",
                "account",
                non_cash,
                compare_non_cash,
            ),
            total_node(
                "Non-cash adjustments Total",
                non_cash,
                compare_non_cash,
            ),
        ],
    )
    operating = make_node(
        "operating_activities",
        "Cash Flow from Operating Activities",
        "section",
        children=[
            make_node(
                "net_income",
                "Net Income",
                "line",
                income,
                compare_income,
            ),
            non_cash_group,
            total_node(
                "Net cash provided by Operating Activities",
                operating_amount,
                compare_operating,
            ),
        ],
    )
    operating["children"][-1] = total_node(
        "Net cash provided by Operating Activities",
        operating["amount_value"],
        operating["compare_amount_value"],
    )
    investing = make_node(
        "investing_activities",
        "Cash Flow from Investing Activities",
        "section",
        children=[
            total_node(
                "Net cash provided by Investing Activities",
                investing_amount,
                compare_investing if compare_start else None,
            )
        ],
    )
    financing = make_node(
        "financing_activities",
        "Cash Flow from Financing Activities",
        "section",
        children=[
            total_node(
                "Net cash provided by Financing Activities",
                financing_amount,
                compare_financing if compare_start else None,
            )
        ],
    )
    return [
        make_node(
            "beginning_cash",
            "Beginning Cash Balance",
            "total",
            beginning,
            compare_beginning,
        ),
        operating,
        investing,
        financing,
        make_node(
            "net_change",
            "Net Change in cash",
            "total",
            net_change,
            compare_net_change,
        ),
        make_node(
            "ending_cash",
            "Ending Cash Balance",
            "total",
            ending,
            compare_ending,
        ),
    ]


def build_cash_flow_report(organization, filters):
    country = getattr(organization, "country", None) or "IN"
    date_range = (filters.get("date_range") or "this_month").strip().lower()
    start, end = resolve_date_range(
        date_range,
        filters.get("date_from"),
        filters.get("date_to"),
        country=country,
    )
    basis = (filters.get("report_basis") or "cash").strip().lower()
    if basis not in ("cash", "accrual"):
        basis = "cash"
    filter_accounts = (
        filters.get("filter_accounts") or "without_zero_balance"
    ).strip().lower()
    compare_with = (filters.get("compare_with") or "none").strip().lower()
    compare_start, compare_end = previous_range(start, end, compare_with)
    sections = build_cash_flow_tree(
        organization, start, end, basis, compare_start, compare_end
    )
    sections = filter_zero_nodes(sections, filter_accounts == "all_accounts")
    payload = organization_payload(organization)
    payload.update(
        {
            "key": "cash_flow_statement",
            "title": "Cash Flow Statement",
            "basis": basis,
            "basis_label": f"Basis : {'Cash' if basis == 'cash' else 'Accrual'}",
            "date_range": date_range,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "date_from_display": format_report_date(start),
            "date_to_display": format_report_date(end),
            "period_display": f"From {format_report_date(start)} To {format_report_date(end)}",
            "filter_accounts": filter_accounts,
            "compare_with": compare_with,
            "compare_date_from": compare_start.isoformat() if compare_start else None,
            "compare_date_to": compare_end.isoformat() if compare_end else None,
            "columns": report_columns(end, compare_end),
            "sections": strip_internal(sections),
            "rows": flatten_nodes(sections),
            "totals": {
                "beginning_cash": next(
                    (
                        row["amount"]
                        for row in flatten_nodes(sections)
                        if row["key"] == "beginning_cash"
                    ),
                    money_text(ZERO),
                ),
                "net_change": next(
                    (
                        row["amount"]
                        for row in flatten_nodes(sections)
                        if row["key"] == "net_change"
                    ),
                    money_text(ZERO),
                ),
                "ending_cash": next(
                    (
                        row["amount"]
                        for row in flatten_nodes(sections)
                        if row["key"] == "ending_cash"
                    ),
                    money_text(ZERO),
                ),
            },
        }
    )
    return payload


BUILDERS = {
    "balance_sheet": build_balance_sheet_report,
    "profit_and_loss": build_profit_and_loss_report,
    "cash_flow_statement": build_cash_flow_report,
}


def default_export_options():
    return {
        "export_file_name": "",
        "password_protect": False,
        "password": "",
        "language": "en",
        "display": {
            "organization_name": True,
            "organization_details": False,
            "report_basis": True,
            "page_number": False,
            "generated_by": False,
            "generated_date": False,
            "generated_time": False,
        },
        "column_headers_on_each_page": True,
        "temporary_note": "",
        "table_density": "classic",
        "auto_resize_table": True,
        "paper_size": "A4",
        "orientation": "portrait",
        "margins": {
            "top": "0.7",
            "bottom": "0.55",
            "left": "0.2",
            "right": "0.2",
        },
    }


def export_form_payload(report_key, title=None):
    meta = next((item for item in FINANCIAL_REPORTS if item["key"] == report_key), None)
    label = title or (meta["label"] if meta else "Report")
    options = default_export_options()
    options["export_file_name"] = label.replace(" ", "_")
    return {
        "title": "Export Report as PDF",
        "fields": {
            "export_file_name": {
                "label": "Export File Name",
                "required": False,
            },
            "password_protect": {
                "label": "I want to protect this file with a password.",
                "required": False,
                "default": False,
            },
            "password": {"label": "Password", "required": False},
            "language": {
                "label": "Select the language in which you want to export the report as PDF",
                "choices": list(LANGUAGE_CHOICES),
                "default": "en",
            },
            "display": {
                "label": "Choose Details to Display",
                "choices": [
                    {"value": "organization_name", "label": "Organization Name", "default": True},
                    {"value": "organization_details", "label": "Organization Details", "default": False},
                    {"value": "report_basis", "label": "Report Basis", "default": True},
                    {"value": "page_number", "label": "Page Number", "default": False},
                    {"value": "generated_by", "label": "Generated By", "default": False},
                    {"value": "generated_date", "label": "Generated Date", "default": False},
                    {"value": "generated_time", "label": "Generated Time", "default": False},
                ],
            },
            "column_headers_on_each_page": {
                "label": "Column Headers on Each Page",
                "default": True,
            },
            "temporary_note": {
                "label": "Temporary Note",
                "help": "Enter any additional information about this report as a note to display it at the footer of the report when it is exported.",
            },
            "table_density": {
                "label": "Table Density",
                "choices": list(TABLE_DENSITY_CHOICES),
                "default": "classic",
            },
            "auto_resize_table": {
                "label": "Re-size the table and its font automatically to fit the content within the table.",
                "default": True,
            },
            "paper_size": {
                "label": "Paper Size",
                "choices": list(PAPER_SIZE_CHOICES),
                "default": "A4",
            },
            "orientation": {
                "label": "Orientation",
                "choices": list(ORIENTATION_CHOICES),
                "default": "portrait",
            },
            "margins": {
                "label": "Margins",
                "top": "0.7",
                "bottom": "0.55",
                "left": "0.2",
                "right": "0.2",
            },
        },
        "defaults": options,
        "preview": {
            "organization_name": True,
            "report_basis": True,
        },
        "note": "The details you select above will be displayed only for this export.",
    }


def balance_sheet_form_payload():
    today = date.today()
    return {
        "title": "Balance Sheet",
        "fields": {
            "as_of_date": {
                "label": "As of Date",
                "required": True,
                "choices": list(AS_OF_DATE_CHOICES),
                "default": "today",
            },
            "report_date": {
                "label": "Report Date",
                "required": False,
                "default": today.isoformat(),
                "display": format_report_date(today),
            },
            "report_basis": {
                "label": "Report Basis",
                "required": True,
                "choices": list(REPORT_BASIS_CHOICES),
                "default": "cash",
            },
            "filter_accounts": {
                "label": "Filter Accounts",
                "required": False,
                "choices": list(FILTER_ACCOUNTS_CHOICES),
                "default": "without_zero_balance",
            },
            "compare_with": {
                "label": "Compare With",
                "section": "COMPARE",
                "help": "Compare Based on Period/Year",
                "choices": list(COMPARE_WITH_CHOICES),
                "default": "none",
            },
        },
        "actions": {"run": "Run Report"},
        "export_form_path": "/api/reports/financial/balance-sheet/export-form/",
    }


def period_form_payload(title, export_form_path):
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
            "report_basis": {
                "label": "Report Basis",
                "required": True,
                "choices": list(REPORT_BASIS_CHOICES),
                "default": "cash",
            },
            "filter_accounts": {
                "label": "Filter Accounts",
                "required": False,
                "choices": list(FILTER_ACCOUNTS_CHOICES),
                "default": "without_zero_balance",
            },
            "compare_with": {
                "label": "Compare With",
                "section": "COMPARE",
                "help": "Compare Based on Period/Year",
                "choices": list(COMPARE_WITH_CHOICES),
                "default": "none",
            },
        },
        "actions": {"run": "Run Report"},
        "export_form_path": export_form_path,
    }


def form_payload(report_key):
    if report_key == "balance_sheet":
        return balance_sheet_form_payload()
    if report_key == "profit_and_loss":
        return period_form_payload(
            "Profit and Loss",
            "/api/reports/financial/profit-and-loss/export-form/",
        )
    return period_form_payload(
        "Cash Flow Statement",
        "/api/reports/financial/cash-flow-statement/export-form/",
    )
