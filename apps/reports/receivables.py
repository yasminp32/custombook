from apps.credit_notes.models import CreditNote
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.payments_received.models import PaymentReceived
from apps.reports.financial import (
    ACTIVE_INVOICE,
    AS_OF_DATE_CHOICES,
    DATE_RANGE_CHOICES,
    ZERO,
    format_report_date,
    money,
    money_display,
    money_text,
    organization_payload,
    resolve_as_of_date,
    resolve_date_range,
)

RECEIVABLE_REPORTS = (
    {
        "key": "customer_balance_summary",
        "label": "Customer Balance Summary",
        "path": "/api/reports/receivables/customer-balance-summary/",
        "form_path": "/api/reports/receivables/customer-balance-summary/form/",
        "export_path": "/api/reports/receivables/customer-balance-summary/export/",
    },
    {
        "key": "ar_aging_summary",
        "label": "AR Aging Summary",
        "path": "/api/reports/receivables/ar-aging-summary/",
        "form_path": "/api/reports/receivables/ar-aging-summary/form/",
        "export_path": "/api/reports/receivables/ar-aging-summary/export/",
    },
    {
        "key": "ar_aging_details",
        "label": "AR Aging Details",
        "path": "/api/reports/receivables/ar-aging-details/",
        "form_path": "/api/reports/receivables/ar-aging-details/form/",
        "export_path": "/api/reports/receivables/ar-aging-details/export/",
    },
)

EMPTY_BALANCE_MESSAGE = "There were no customer balances for the selected date range."


def receivables_date_form_payload(title, export_form_path):
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


def customer_balance_summary_form_payload():
    return receivables_date_form_payload(
        "Customer Balance Summary",
        "/api/reports/receivables/customer-balance-summary/export-form/",
    )


def currency_amount(symbol, value):
    return f"{symbol}{money_display(value)}"


def closing_parts(symbol, value):
    amount = money(value)
    display = currency_amount(symbol, abs(amount))
    if amount > 0:
        return display, "Dr", f"{display} Dr"
    if amount < 0:
        return display, "Cr", f"{display} Cr"
    return display, "", display


def customer_name(customer):
    return (customer.display_name or customer.company_name or "").strip() or "Untitled"


def build_customer_balance_summary_report(organization, filters):
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

    def bucket_for(customer_id, name=""):
        key = str(customer_id) if customer_id else "none"
        return grouped.setdefault(
            key,
            {
                "customer_id": str(customer_id) if customer_id else None,
                "customer_name": name or "Untitled",
                "invoiced_amount": ZERO,
                "amount_received": ZERO,
                "closing_balance": ZERO,
            },
        )

    for customer in Customer.objects.filter(organization=organization):
        bucket = bucket_for(customer.id, customer_name(customer))
        bucket["closing_balance"] += money(customer.opening_balance or 0)

    invoices = (
        Invoice.objects.filter(
            organization=organization,
            invoice_date__lte=end,
        )
        .filter(ACTIVE_INVOICE)
        .select_related("customer")
    )
    for invoice in invoices:
        customer = invoice.customer
        bucket = bucket_for(
            customer.id if customer else None,
            customer_name(customer) if customer else "No customer",
        )
        amount = money(invoice.total_amount)
        bucket["closing_balance"] += amount
        if start <= invoice.invoice_date <= end:
            bucket["invoiced_amount"] += amount

    payments = PaymentReceived.objects.filter(
        organization=organization,
        payment_date__lte=end,
    ).select_related("customer")
    for payment in payments:
        customer = payment.customer
        bucket = bucket_for(
            customer.id if customer else None,
            customer_name(customer) if customer else "No customer",
        )
        amount = money(payment.amount)
        bucket["closing_balance"] -= amount
        if start <= payment.payment_date <= end:
            bucket["amount_received"] += amount

    credit_notes = (
        CreditNote.objects.filter(
            organization=organization,
            credit_note_date__lte=end,
        )
        .exclude(status__in=(CreditNote.Status.DRAFT, CreditNote.Status.VOID))
        .select_related("customer")
    )
    for note in credit_notes:
        customer = note.customer
        bucket = bucket_for(
            customer.id if customer else None,
            customer_name(customer) if customer else "No customer",
        )
        bucket["closing_balance"] -= money(note.amount)

    rows = []
    total_invoiced = ZERO
    total_received = ZERO
    total_closing = ZERO
    for bucket in sorted(grouped.values(), key=lambda item: item["customer_name"].lower()):
        invoiced = bucket["invoiced_amount"]
        received = bucket["amount_received"]
        closing = bucket["closing_balance"]
        if invoiced == ZERO and received == ZERO and closing == ZERO:
            continue
        total_invoiced += invoiced
        total_received += received
        total_closing += closing
        closing_display, closing_side, closing_label = closing_parts(symbol, closing)
        rows.append(
            {
                "customer_id": bucket["customer_id"],
                "customer_name": bucket["customer_name"],
                "label": bucket["customer_name"],
                "invoiced_amount": money_text(invoiced),
                "invoiced_amount_display": currency_amount(symbol, invoiced),
                "amount_received": money_text(received),
                "amount_received_display": currency_amount(symbol, received),
                "closing_balance": money_text(closing),
                "closing_balance_display": closing_label,
                "closing_balance_amount_display": closing_display,
                "closing_balance_side": closing_side,
            }
        )

    total_display, total_side, total_label = closing_parts(symbol, total_closing)
    payload = organization_payload(organization)
    payload.update(
        {
            "key": "customer_balance_summary",
            "title": "Customer Balance Summary",
            "section": "receivables",
            "section_label": "Receivables",
            "date_range": date_range,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "date_from_display": format_report_date(start),
            "date_to_display": format_report_date(end),
            "period_display": f"From {format_report_date(start)} To {format_report_date(end)}",
            "basis_label": "Basis: Cash",
            "columns": [
                {"key": "customer_name", "label": "CUSTOMER NAME"},
                {"key": "invoiced_amount", "label": "INVOICED AMOUNT"},
                {"key": "amount_received", "label": "AMOUNT RECEIVED"},
                {"key": "closing_balance", "label": "CLOSING BALANCE"},
            ],
            "rows": rows,
            "empty": len(rows) == 0,
            "empty_message": EMPTY_BALANCE_MESSAGE if not rows else "",
            "totals": {
                "label": "Total",
                "invoiced_amount": money_text(total_invoiced),
                "invoiced_amount_display": currency_amount(symbol, total_invoiced),
                "amount_received": money_text(total_received),
                "amount_received_display": currency_amount(symbol, total_received),
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
                "customer_id": None,
                "customer_name": "Total",
                "label": "Total",
                "is_total": True,
                "invoiced_amount": money_text(total_invoiced),
                "invoiced_amount_display": currency_amount(symbol, total_invoiced),
                "amount_received": money_text(total_received),
                "amount_received_display": currency_amount(symbol, total_received),
                "closing_balance": money_text(total_closing),
                "closing_balance_display": total_label,
                "closing_balance_amount_display": total_display,
                "closing_balance_side": total_side,
            }
        )
    return payload


AGING_BUCKETS = (
    ("current", "CURRENT"),
    ("days_1_15", "1-15 DAYS"),
    ("days_16_30", "16-30 DAYS"),
    ("days_31_45", "31-45 DAYS"),
    ("days_46_60", "46-60 DAYS"),
    ("days_61_90", "61-90 DAYS"),
    ("over_90", ">90 DAYS"),
)

EMPTY_AGING_MESSAGE = "There are no outstanding invoices as of the selected date."


def ar_aging_summary_form_payload():
    as_of = resolve_as_of_date("today")
    return {
        "title": "AR Aging Summary",
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
                "default": as_of.isoformat(),
                "display": format_report_date(as_of),
            },
        },
        "actions": {"run": "Run Report"},
        "export_form_path": "/api/reports/receivables/ar-aging-summary/export-form/",
    }


def empty_aging_amounts():
    return {key: ZERO for key, _label in AGING_BUCKETS}


def aging_bucket_key(due_date, as_of):
    if not due_date or due_date >= as_of:
        return "current"
    days = (as_of - due_date).days
    if days <= 15:
        return "days_1_15"
    if days <= 30:
        return "days_16_30"
    if days <= 45:
        return "days_31_45"
    if days <= 60:
        return "days_46_60"
    if days <= 90:
        return "days_61_90"
    return "over_90"


def outstanding_amount(invoice):
    due = money(invoice.total_amount) - money(invoice.amount_paid)
    return due if due > ZERO else ZERO


def aging_row_payload(symbol, customer_id, name, amounts, is_total=False):
    row_total = sum((amounts[key] for key, _label in AGING_BUCKETS), ZERO)
    row = {
        "customer_id": customer_id,
        "customer_name": name,
        "label": name,
        "is_total": is_total,
        "total": money_text(row_total),
        "total_display": currency_amount(symbol, row_total),
    }
    for key, _label in AGING_BUCKETS:
        row[key] = money_text(amounts[key])
        row[f"{key}_display"] = currency_amount(symbol, amounts[key])
    return row


def build_ar_aging_summary_report(organization, filters):
    as_of_key = (filters.get("as_of_date") or "today").strip().lower()
    as_of = resolve_as_of_date(as_of_key, filters.get("report_date"))
    symbol = organization_payload(organization)["currency_symbol"]
    grouped = {}

    invoices = (
        Invoice.objects.filter(
            organization=organization,
            invoice_date__lte=as_of,
        )
        .filter(ACTIVE_INVOICE)
        .select_related("customer")
    )
    for invoice in invoices:
        customer = invoice.customer
        customer_id = str(customer.id) if customer else None
        name = customer_name(customer) if customer else "No customer"
        key = customer_id or "none"
        bucket = grouped.setdefault(
            key,
            {
                "customer_id": customer_id,
                "customer_name": name,
                "amounts": empty_aging_amounts(),
            },
        )
        due = outstanding_amount(invoice)
        if due <= ZERO:
            continue
        bucket_key = aging_bucket_key(invoice.due_date or invoice.invoice_date, as_of)
        bucket["amounts"][bucket_key] += due

    rows = []
    totals = empty_aging_amounts()
    for bucket in sorted(grouped.values(), key=lambda item: item["customer_name"].lower()):
        amounts = bucket["amounts"]
        for key, _label in AGING_BUCKETS:
            totals[key] += amounts[key]
        rows.append(
            aging_row_payload(
                symbol,
                bucket["customer_id"],
                bucket["customer_name"],
                amounts,
            )
        )

    columns = [{"key": "customer_name", "label": "CUSTOMER NAME"}]
    columns.extend({"key": key, "label": label} for key, label in AGING_BUCKETS)
    columns.append({"key": "total", "label": "TOTAL"})

    payload = organization_payload(organization)
    payload.update(
        {
            "key": "ar_aging_summary",
            "title": "AR Aging Summary",
            "section": "receivables",
            "section_label": "Receivables",
            "as_of_date": as_of_key,
            "report_date": as_of.isoformat(),
            "as_of_display": f"As of {format_report_date(as_of)}",
            "basis_label": "Basis: Cash",
            "columns": columns,
            "rows": rows,
            "empty": len(rows) == 0,
            "empty_message": EMPTY_AGING_MESSAGE if not rows else "",
            "totals": aging_row_payload(symbol, None, "Total", totals, is_total=True),
        }
    )
    if rows:
        rows.append(aging_row_payload(symbol, None, "Total", totals, is_total=True))
    return payload


AGING_DETAIL_LABELS = {
    "current": "Current",
    "days_1_15": "1 - 15 Days",
    "days_16_30": "16 - 30 Days",
    "days_31_45": "31 - 45 Days",
    "days_46_60": "46 - 60 Days",
    "days_61_90": "61 - 90 Days",
    "over_90": "> 90 Days",
}

EMPTY_AGING_DETAILS_MESSAGE = "There are no outstanding invoices as of the selected date."


def ar_aging_details_form_payload():
    as_of = resolve_as_of_date("today")
    return {
        "title": "AR Aging Details",
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
                "default": as_of.isoformat(),
                "display": format_report_date(as_of),
            },
        },
        "actions": {"run": "Run Report"},
        "export_form_path": "/api/reports/receivables/ar-aging-details/export-form/",
    }


def invoice_age_days(due_date, as_of):
    if not due_date:
        return 0
    return max((as_of - due_date).days, 0)


def invoice_status_label(due_date, as_of):
    if due_date and due_date < as_of:
        return "Overdue"
    return "Open"


def build_ar_aging_details_report(organization, filters):
    as_of_key = (filters.get("as_of_date") or "today").strip().lower()
    as_of = resolve_as_of_date(as_of_key, filters.get("report_date"))
    symbol = organization_payload(organization)["currency_symbol"]
    grouped = {key: [] for key, _label in AGING_BUCKETS}

    invoices = (
        Invoice.objects.filter(
            organization=organization,
            invoice_date__lte=as_of,
        )
        .filter(ACTIVE_INVOICE)
        .select_related("customer")
        .order_by("due_date", "invoice_number")
    )
    for invoice in invoices:
        due = outstanding_amount(invoice)
        if due <= ZERO:
            continue
        due_date = invoice.due_date or invoice.invoice_date
        bucket_key = aging_bucket_key(due_date, as_of)
        customer = invoice.customer
        age_days = invoice_age_days(due_date, as_of)
        grouped[bucket_key].append(
            {
                "invoice_id": str(invoice.id),
                "date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                "date_display": format_report_date(invoice.invoice_date)
                if invoice.invoice_date
                else "",
                "due_date": due_date.isoformat() if due_date else None,
                "due_date_display": format_report_date(due_date) if due_date else "",
                "transaction_number": invoice.invoice_number,
                "type": "Invoice",
                "status": invoice_status_label(due_date, as_of),
                "customer_id": str(customer.id) if customer else None,
                "customer_name": customer_name(customer) if customer else "No customer",
                "age_days": age_days,
                "age": f"{age_days} Days",
                "amount": money_text(due),
                "amount_display": currency_amount(symbol, due),
                "bucket": bucket_key,
                "is_section": False,
                "is_total": False,
            }
        )

    columns = [
        {"key": "date", "label": "DATE"},
        {"key": "due_date", "label": "DUE DATE"},
        {"key": "transaction_number", "label": "TRANSACTION#"},
        {"key": "type", "label": "TYPE"},
        {"key": "status", "label": "STATUS"},
        {"key": "customer_name", "label": "CUSTOMER NAME"},
        {"key": "age", "label": "AGE"},
        {"key": "amount", "label": "AMOUNT"},
    ]
    groups = []
    rows = []
    total_amount = ZERO
    for key, _column_label in AGING_BUCKETS:
        items = grouped[key]
        if not items:
            continue
        group_total = ZERO
        for item in items:
            group_total += money(item["amount"])
        total_amount += group_total
        section_label = AGING_DETAIL_LABELS[key]
        section_row = {
            "date": section_label,
            "date_display": section_label,
            "due_date": "",
            "due_date_display": "",
            "transaction_number": "",
            "type": "",
            "status": "",
            "customer_name": "",
            "age": "",
            "amount": "",
            "amount_display": "",
            "label": section_label,
            "bucket": key,
            "is_section": True,
            "is_total": False,
        }
        rows.append(section_row)
        rows.extend(items)
        groups.append(
            {
                "key": key,
                "label": section_label,
                "rows": items,
                "total": money_text(group_total),
                "total_display": currency_amount(symbol, group_total),
            }
        )

    payload = organization_payload(organization)
    payload.update(
        {
            "key": "ar_aging_details",
            "title": "AR Aging Details",
            "section": "receivables",
            "section_label": "Receivables",
            "as_of_date": as_of_key,
            "report_date": as_of.isoformat(),
            "as_of_display": f"As of {format_report_date(as_of)}",
            "basis_label": "Basis: Cash",
            "columns": columns,
            "groups": groups,
            "rows": rows,
            "empty": len(groups) == 0,
            "empty_message": EMPTY_AGING_DETAILS_MESSAGE if not groups else "",
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
                "date": "Total",
                "date_display": "Total",
                "due_date": "",
                "due_date_display": "",
                "transaction_number": "",
                "type": "",
                "status": "",
                "customer_name": "",
                "age": "",
                "amount": money_text(total_amount),
                "amount_display": currency_amount(symbol, total_amount),
                "label": "Total",
                "is_section": False,
                "is_total": True,
            }
        )
    return payload
