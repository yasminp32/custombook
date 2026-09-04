from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.db.models.functions import Coalesce

from apps.banking.models import BankAccount, BankTransaction
from apps.banking.periods import DATE_RANGE_LABELS, DATE_RANGES, each_date, get_date_range

ZERO = Decimal("0.00")


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def currency_label(code):
    from apps.banking.constants import BANKING_CURRENCIES

    for option in BANKING_CURRENCIES:
        if option["value"] == code:
            return option["label"]
    return code


def resolve_accounts(organization, account_id=None, status=BankAccount.Status.ACTIVE):
    queryset = BankAccount.objects.filter(organization=organization)
    if status:
        queryset = queryset.filter(status=status)
    if account_id and account_id != "all":
        queryset = queryset.filter(pk=account_id)
    return queryset


def build_chart(accounts, start, end):
    account_ids = list(accounts.values_list("id", flat=True))
    current_total = accounts.aggregate(total=Coalesce(Sum("books_balance"), ZERO))["total"] or ZERO
    if not account_ids:
        return [
            {
                "date": day.isoformat(),
                "date_label": day.strftime("%d %b"),
                "balance": money(0),
            }
            for day in each_date(start, end)
        ]

    transactions = BankTransaction.objects.filter(
        account_id__in=account_ids,
        transaction_date__gte=start,
        transaction_date__lte=end,
    )
    by_day = defaultdict(lambda: ZERO)
    period_net = ZERO
    for txn in transactions:
        by_day[txn.transaction_date] += txn.signed_amount
        period_net += txn.signed_amount

    running = current_total - period_net
    points = []
    for day in each_date(start, end):
        running += by_day[day]
        points.append(
            {
                "date": day.isoformat(),
                "date_label": day.strftime("%d %b"),
                "balance": money(running),
            }
        )
    return points


def build_overview(organization, query_params):
    range_key, range_label, start, end = get_date_range(query_params.get("date_range"))
    account_id = query_params.get("account_id") or "all"
    accounts = resolve_accounts(organization, account_id)
    all_active = BankAccount.objects.filter(
        organization=organization,
        status=BankAccount.Status.ACTIVE,
    )

    cash_accounts = accounts.filter(
        account_type__in=[
            BankAccount.AccountType.CASH,
            BankAccount.AccountType.UNDEPOSITED_FUNDS,
        ]
    )
    bank_accounts = accounts.filter(account_type=BankAccount.AccountType.BANK)
    cash_in_hand = cash_accounts.aggregate(total=Coalesce(Sum("books_balance"), ZERO))["total"] or ZERO
    bank_balance = bank_accounts.aggregate(total=Coalesce(Sum("books_balance"), ZERO))["total"] or ZERO

    selected_account = None
    account_label = "All Accounts"
    if account_id and account_id != "all":
        selected_account = all_active.filter(pk=account_id).first()
        if selected_account:
            account_label = selected_account.name
            if selected_account.is_cash_like:
                cash_in_hand = selected_account.books_balance or ZERO
                bank_balance = ZERO
            elif selected_account.account_type == BankAccount.AccountType.BANK:
                cash_in_hand = ZERO
                bank_balance = selected_account.books_balance or ZERO
            else:
                cash_in_hand = ZERO
                bank_balance = ZERO

    account_options = [{"account_id": "all", "name": "All Accounts", "account_type": "all"}]
    account_options.extend(
        {
            "account_id": str(account.id),
            "name": account.name,
            "account_type": account.account_type,
        }
        for account in all_active.order_by("name")
    )

    serialized_accounts = []
    for account in accounts.order_by("name"):
        serialized_accounts.append(
            {
                "account_id": str(account.id),
                "name": account.name,
                "account_type": account.account_type,
                "account_type_label": account.get_account_type_display(),
                "icon": account.icon,
                "currency": account.currency,
                "books_balance": money(account.books_balance),
                "bank_balance": money(account.bank_balance),
                "books_balance_label": "Amount In Zoho Books",
                "bank_balance_label": "Amount In Bank",
                "is_primary": account.is_primary,
                "status": account.status,
            }
        )

    return {
        "title": "Banking Overview",
        "subtitle": "Track your accounts & transactions",
        "currency": organization.currency or "INR",
        "date_range": range_key,
        "date_range_label": range_label,
        "available_date_ranges": [
            {"key": key, "label": DATE_RANGE_LABELS[key]} for key in DATE_RANGES
        ],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "account_id": str(selected_account.id) if selected_account else "all",
        "account_label": account_label,
        "account_options": account_options,
        "cash_in_hand": money(cash_in_hand),
        "bank_balance": money(bank_balance),
        "chart": build_chart(accounts, start, end),
        "accounts_count": accounts.count(),
        "accounts": serialized_accounts,
        "actions": [
            {"key": "refresh", "label": "Refresh", "path": "/api/banking/refresh/"},
            {
                "key": "export_statement",
                "label": "Export statement",
                "path": "/api/banking/statements/export/",
            },
        ],
    }
