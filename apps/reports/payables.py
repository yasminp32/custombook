from apps.bills.models import Bill
from apps.payments_made.models import PaymentMade
from apps.reports.financial import (
    ACTIVE_BILL,
    ACTIVE_VENDOR_CREDIT,
    DATE_RANGE_CHOICES,
    ZERO,
    format_report_date,
    money,
    money_display,
    money_text,
    organization_payload,
    resolve_date_range,
)
from apps.vendor_credits.models import VendorCredit
from apps.vendors.models import Vendor

PAYABLE_REPORTS = (
    {
        "key": "payments_made",
        "label": "Payments Made",
        "path": "/api/reports/payables/payments-made/",
        "form_path": "/api/reports/payables/payments-made/form/",
        "export_path": "/api/reports/payables/payments-made/export/",
    },
    {
        "key": "vendor_balance_summary",
        "label": "Vendor Balance Summary",
        "path": "/api/reports/payables/vendor-balance-summary/",
        "form_path": "/api/reports/payables/vendor-balance-summary/form/",
        "export_path": "/api/reports/payables/vendor-balance-summary/export/",
    },
)

EMPTY_PAYMENTS_MADE_MESSAGE = "There are no transactions during the selected date range."
EMPTY_VENDOR_BALANCE_MESSAGE = "No vendor data during the selected date range."


def currency_amount(symbol, value):
    return f"{symbol}{money_display(value)}"


def vendor_name(vendor):
    if not vendor:
        return ""
    return (vendor.display_name or vendor.company_name or "").strip()


def payables_date_form_payload(title, export_form_path):
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


def payments_made_form_payload():
    return payables_date_form_payload(
        "Payments Made",
        "/api/reports/payables/payments-made/export-form/",
    )


def build_payments_made_report(organization, filters):
    country = getattr(organization, "country", None) or "IN"
    date_range = (filters.get("date_range") or "this_month").strip().lower()
    start, end = resolve_date_range(
        date_range,
        filters.get("date_from"),
        filters.get("date_to"),
        country=country,
    )
    symbol = organization_payload(organization)["currency_symbol"]
    payments = (
        PaymentMade.objects.filter(
            organization=organization,
            payment_date__range=(start, end),
        )
        .select_related("vendor")
        .order_by("payment_date", "payment_number")
    )

    rows = []
    total_amount = ZERO
    for payment in payments:
        amount = money(payment.amount)
        total_amount += amount
        rows.append(
            {
                "payment_id": str(payment.id),
                "payment_number": payment.payment_number or "",
                "date": payment.payment_date.isoformat() if payment.payment_date else "",
                "date_display": format_report_date(payment.payment_date)
                if payment.payment_date
                else "",
                "vendor": vendor_name(payment.vendor),
                "vendor_display": vendor_name(payment.vendor),
                "amount": money_text(amount),
                "amount_display": currency_amount(symbol, amount),
                "label": payment.payment_number or "",
                "is_total": False,
            }
        )

    payload = organization_payload(organization)
    payload.update(
        {
            "key": "payments_made",
            "title": "Payments Made",
            "section": "payables",
            "section_label": "Payables",
            "date_range": date_range,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "date_from_display": format_report_date(start),
            "date_to_display": format_report_date(end),
            "period_display": f"From {format_report_date(start)} To {format_report_date(end)}",
            "basis_label": "Basis: Cash",
            "columns": [
                {"key": "payment_number", "label": "PAYMENT NUMBER"},
                {"key": "date", "label": "DATE"},
                {"key": "vendor", "label": "VENDOR"},
                {"key": "amount", "label": "AMOUNT"},
            ],
            "rows": rows,
            "empty": len(rows) == 0,
            "empty_message": EMPTY_PAYMENTS_MADE_MESSAGE if not rows else "",
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
                "payment_id": None,
                "payment_number": "Total",
                "date": "",
                "date_display": "",
                "vendor": "",
                "vendor_display": "",
                "amount": money_text(total_amount),
                "amount_display": currency_amount(symbol, total_amount),
                "label": "Total",
                "is_total": True,
            }
        )
    return payload


def vendor_balance_summary_form_payload():
    return payables_date_form_payload(
        "Vendor Balance Summary",
        "/api/reports/payables/vendor-balance-summary/export-form/",
    )


def closing_parts(symbol, value):
    amount = money(value)
    display = currency_amount(symbol, abs(amount))
    if amount > 0:
        return display, "Cr", f"{display} Cr"
    if amount < 0:
        return display, "Dr", f"{display} Dr"
    return display, "", display


def build_vendor_balance_summary_report(organization, filters):
    country = getattr(organization, "country", None) or "IN"
    date_range = (filters.get("date_range") or "this_month").strip().lower()
    start, end = resolve_date_range(
        date_range,
        filters.get("date_from"),
        filters.get("date_to"),
        country=country,
    )
    symbol = organization_payload(organization)["currency_symbol"]
    grouped = {}

    def bucket_for(vendor_id, name=""):
        key = str(vendor_id) if vendor_id else "none"
        return grouped.setdefault(
            key,
            {
                "vendor_id": str(vendor_id) if vendor_id else None,
                "vendor_name": name or "Untitled",
                "billed_amount": ZERO,
                "amount_paid": ZERO,
                "closing_balance": ZERO,
            },
        )

    for vendor in Vendor.objects.filter(organization=organization):
        bucket = bucket_for(vendor.id, vendor_name(vendor) or "Untitled")
        bucket["closing_balance"] += money(vendor.opening_balance or 0)

    bills = (
        Bill.objects.filter(
            organization=organization,
            bill_date__lte=end,
        )
        .filter(ACTIVE_BILL)
        .select_related("vendor")
    )
    for bill in bills:
        vendor = bill.vendor
        bucket = bucket_for(
            vendor.id if vendor else None,
            vendor_name(vendor) if vendor else "No vendor",
        )
        amount = money(bill.amount)
        bucket["closing_balance"] += amount
        if start <= bill.bill_date <= end:
            bucket["billed_amount"] += amount

    payments = PaymentMade.objects.filter(
        organization=organization,
        payment_date__lte=end,
    ).select_related("vendor")
    for payment in payments:
        vendor = payment.vendor
        bucket = bucket_for(
            vendor.id if vendor else None,
            vendor_name(vendor) if vendor else "No vendor",
        )
        amount = money(payment.amount)
        bucket["closing_balance"] -= amount
        if start <= payment.payment_date <= end:
            bucket["amount_paid"] += amount

    credits = (
        VendorCredit.objects.filter(
            organization=organization,
            credit_date__lte=end,
        )
        .filter(ACTIVE_VENDOR_CREDIT)
        .select_related("vendor")
    )
    for credit in credits:
        vendor = credit.vendor
        bucket = bucket_for(
            vendor.id if vendor else None,
            vendor_name(vendor) if vendor else "No vendor",
        )
        bucket["closing_balance"] -= money(credit.amount)

    rows = []
    total_billed = ZERO
    total_paid = ZERO
    total_closing = ZERO
    for bucket in sorted(grouped.values(), key=lambda item: item["vendor_name"].lower()):
        billed = bucket["billed_amount"]
        paid = bucket["amount_paid"]
        closing = bucket["closing_balance"]
        if billed == ZERO and paid == ZERO and closing == ZERO:
            continue
        total_billed += billed
        total_paid += paid
        total_closing += closing
        closing_display, closing_side, closing_label = closing_parts(symbol, closing)
        rows.append(
            {
                "vendor_id": bucket["vendor_id"],
                "vendor_name": bucket["vendor_name"],
                "label": bucket["vendor_name"],
                "billed_amount": money_text(billed),
                "billed_amount_display": currency_amount(symbol, billed),
                "amount_paid": money_text(paid),
                "amount_paid_display": currency_amount(symbol, paid),
                "closing_balance": money_text(closing),
                "closing_balance_display": closing_label,
                "closing_balance_amount_display": closing_display,
                "closing_balance_side": closing_side,
                "is_total": False,
            }
        )

    total_display, total_side, total_label = closing_parts(symbol, total_closing)
    payload = organization_payload(organization)
    payload.update(
        {
            "key": "vendor_balance_summary",
            "title": "Vendor Balance Summary",
            "section": "payables",
            "section_label": "Payables",
            "date_range": date_range,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "date_from_display": format_report_date(start),
            "date_to_display": format_report_date(end),
            "period_display": f"From {format_report_date(start)} To {format_report_date(end)}",
            "basis_label": "Basis: Cash",
            "columns": [
                {"key": "vendor_name", "label": "VENDOR NAME"},
                {"key": "billed_amount", "label": "BILLED AMOUNT"},
                {"key": "amount_paid", "label": "AMOUNT PAID"},
                {"key": "closing_balance", "label": "CLOSING BALANCE"},
            ],
            "rows": rows,
            "empty": len(rows) == 0,
            "empty_message": EMPTY_VENDOR_BALANCE_MESSAGE if not rows else "",
            "totals": {
                "label": "Total",
                "billed_amount": money_text(total_billed),
                "billed_amount_display": currency_amount(symbol, total_billed),
                "amount_paid": money_text(total_paid),
                "amount_paid_display": currency_amount(symbol, total_paid),
                "closing_balance": money_text(total_closing),
                "closing_balance_display": total_label,
                "closing_balance_amount_display": total_display,
                "closing_balance_side": total_side,
            },
        }
    )
    if rows:
        rows.append(
            {
                "vendor_id": None,
                "vendor_name": "Total",
                "label": "Total",
                "is_total": True,
                "billed_amount": money_text(total_billed),
                "billed_amount_display": currency_amount(symbol, total_billed),
                "amount_paid": money_text(total_paid),
                "amount_paid_display": currency_amount(symbol, total_paid),
                "closing_balance": money_text(total_closing),
                "closing_balance_display": total_label,
                "closing_balance_amount_display": total_display,
                "closing_balance_side": total_side,
            }
        )
    return payload
