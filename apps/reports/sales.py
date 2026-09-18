from decimal import Decimal

from django.db.models import Q

from apps.credit_notes.models import CreditNote
from apps.invoices.models import Invoice, InvoiceLine
from apps.reports.financial import (
    ACTIVE_INVOICE,
    DATE_RANGE_CHOICES,
    ZERO,
    format_report_date,
    money,
    money_display,
    money_text,
    organization_payload,
    resolve_date_range,
)

SALES_REPORTS = (
    {
        "key": "sales_by_customer",
        "label": "Sales by Customer",
        "path": "/api/reports/sales/sales-by-customer/",
        "form_path": "/api/reports/sales/sales-by-customer/form/",
        "export_path": "/api/reports/sales/sales-by-customer/export/",
    },
    {
        "key": "sales_by_item",
        "label": "Sales by Item",
        "path": "/api/reports/sales/sales-by-item/",
        "form_path": "/api/reports/sales/sales-by-item/form/",
        "export_path": "/api/reports/sales/sales-by-item/export/",
    },
    {
        "key": "sales_by_sales_person",
        "label": "Sales by Sales Person",
        "path": "/api/reports/sales/sales-by-sales-person/",
        "form_path": "/api/reports/sales/sales-by-sales-person/form/",
        "export_path": "/api/reports/sales/sales-by-sales-person/export/",
    },
)

EMPTY_SALES_MESSAGE = "There were no sales during the selected date range."


def sales_date_form_payload(title, export_form_path):
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


def sales_by_customer_form_payload():
    return sales_date_form_payload(
        "Sales by Customer",
        "/api/reports/sales/sales-by-customer/export-form/",
    )


def sales_by_item_form_payload():
    return sales_date_form_payload(
        "Sales by Item",
        "/api/reports/sales/sales-by-item/export-form/",
    )


def sales_by_sales_person_form_payload():
    return sales_date_form_payload(
        "Sales by Sales Person",
        "/api/reports/sales/sales-by-sales-person/export-form/",
    )


def salesperson_bucket_key(salesperson_id, salesperson_name):
    if salesperson_id:
        return str(salesperson_id)
    name = (salesperson_name or "").strip()
    if name:
        return f"name:{name.lower()}"
    return "unassigned"


def salesperson_display_name(salesperson_name):
    name = (salesperson_name or "").strip()
    return name or "Unassigned"


def get_or_create_salesperson_bucket(grouped, salesperson_id, salesperson_name):
    key = salesperson_bucket_key(salesperson_id, salesperson_name)
    return grouped.setdefault(
        key,
        {
            "salesperson_id": str(salesperson_id) if salesperson_id else None,
            "name": salesperson_display_name(salesperson_name),
            "invoice_count": 0,
            "invoice_sales": ZERO,
            "invoice_sales_with_tax": ZERO,
            "credit_note_count": 0,
            "credit_note_sales": ZERO,
        },
    )


def quantity_display(value):
    quantity = Decimal(value or 0)
    if quantity == quantity.to_integral_value():
        return str(int(quantity))
    return f"{quantity:.2f}"


def build_sales_by_customer_report(organization, filters):
    country = getattr(organization, "country", None) or "IN"
    date_range = (filters.get("date_range") or "this_month").strip().lower()
    start, end = resolve_date_range(
        date_range,
        filters.get("date_from"),
        filters.get("date_to"),
        country=country,
    )
    invoices = (
        Invoice.objects.filter(
            organization=organization,
            invoice_date__range=(start, end),
        )
        .filter(ACTIVE_INVOICE)
        .select_related("customer")
        .prefetch_related("lines")
    )
    grouped = {}
    for invoice in invoices:
        customer = invoice.customer
        customer_id = str(customer.id) if customer else None
        name = ""
        if customer:
            name = customer.display_name or customer.company_name or ""
        if not name:
            name = "No customer"
        bucket = grouped.setdefault(
            customer_id or "none",
            {
                "customer_id": customer_id,
                "name": name,
                "invoice_count": 0,
                "sales": ZERO,
                "sales_with_tax": ZERO,
            },
        )
        line_total = ZERO
        for line in invoice.lines.all():
            line_total += money(line.amount)
        with_tax = money(invoice.total_amount)
        bucket["invoice_count"] += 1
        bucket["sales"] += line_total if line_total else with_tax
        bucket["sales_with_tax"] += with_tax

    rows = []
    total_invoices = 0
    total_sales = ZERO
    total_with_tax = ZERO
    for bucket in sorted(grouped.values(), key=lambda item: item["sales_with_tax"], reverse=True):
        total_invoices += bucket["invoice_count"]
        total_sales += bucket["sales"]
        total_with_tax += bucket["sales_with_tax"]
        rows.append(
            {
                "customer_id": bucket["customer_id"],
                "name": bucket["name"],
                "label": bucket["name"],
                "invoice_count": bucket["invoice_count"],
                "sales": money_text(bucket["sales"]),
                "sales_display": money_display(bucket["sales"]),
                "sales_with_tax": money_text(bucket["sales_with_tax"]),
                "sales_with_tax_display": money_display(bucket["sales_with_tax"]),
                "amount": money_text(bucket["sales_with_tax"]),
                "amount_display": money_display(bucket["sales_with_tax"]),
            }
        )

    payload = organization_payload(organization)
    payload.update(
        {
            "key": "sales_by_customer",
            "title": "Sales by Customer",
            "section": "sales",
            "section_label": "Sales",
            "date_range": date_range,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "date_from_display": format_report_date(start),
            "date_to_display": format_report_date(end),
            "period_display": f"From {format_report_date(start)} To {format_report_date(end)}",
            "basis_label": "Basis: Cash",
            "columns": [
                {"key": "name", "label": "NAME"},
                {"key": "invoice_count", "label": "INVOICE COUNT"},
                {"key": "sales", "label": "SALES"},
                {"key": "sales_with_tax", "label": "SALES WITH TAX"},
            ],
            "rows": rows,
            "empty": len(rows) == 0,
            "empty_message": EMPTY_SALES_MESSAGE if not rows else "",
            "totals": {
                "invoice_count": total_invoices,
                "sales": money_text(total_sales),
                "sales_display": money_display(total_sales),
                "sales_with_tax": money_text(total_with_tax),
                "sales_with_tax_display": money_display(total_with_tax),
            },
        }
    )
    return payload


def build_sales_by_item_report(organization, filters):
    country = getattr(organization, "country", None) or "IN"
    date_range = (filters.get("date_range") or "this_month").strip().lower()
    start, end = resolve_date_range(
        date_range,
        filters.get("date_from"),
        filters.get("date_to"),
        country=country,
    )
    lines = (
        InvoiceLine.objects.filter(
            invoice__organization=organization,
            invoice__invoice_date__range=(start, end),
        )
        .filter(~Q(invoice__status__in=(Invoice.Status.DRAFT, Invoice.Status.CANCELLED)))
        .select_related("item", "invoice")
        .order_by("name", "id")
    )
    grouped = {}
    for line in lines:
        item = line.item
        key = str(item.id) if item is not None else f"name:{(line.name or '').strip().lower()}"
        bucket = grouped.setdefault(
            key,
            {
                "item_id": str(item.id) if item is not None else None,
                "item_name": (item.name if item is not None else line.name) or "Untitled",
                "sku": (item.sku if item is not None else "") or "",
                "quantity_sold": ZERO,
                "amount": ZERO,
            },
        )
        bucket["quantity_sold"] += Decimal(line.quantity or 0)
        bucket["amount"] += money(line.amount)

    rows = []
    total_qty = ZERO
    total_amount = ZERO
    for bucket in sorted(
        grouped.values(),
        key=lambda row: (-row["amount"], row["item_name"].lower()),
    ):
        quantity = bucket["quantity_sold"]
        amount = bucket["amount"]
        average = (amount / quantity) if quantity else ZERO
        total_qty += quantity
        total_amount += amount
        rows.append(
            {
                "item_id": bucket["item_id"],
                "item_name": bucket["item_name"],
                "label": bucket["item_name"],
                "sku": bucket["sku"],
                "quantity_sold": quantity_display(quantity),
                "amount": money_text(amount),
                "amount_display": money_display(amount),
                "average_price": money_text(average),
                "average_price_display": money_display(average),
            }
        )

    payload = organization_payload(organization)
    payload.update(
        {
            "key": "sales_by_item",
            "title": "Sales by Item",
            "section": "sales",
            "section_label": "Sales",
            "date_range": date_range,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "date_from_display": format_report_date(start),
            "date_to_display": format_report_date(end),
            "period_display": f"From {format_report_date(start)} To {format_report_date(end)}",
            "basis_label": "Basis: Cash",
            "columns": [
                {"key": "item_name", "label": "ITEM NAME"},
                {"key": "sku", "label": "SKU"},
                {"key": "quantity_sold", "label": "QUANTITY SOLD"},
                {"key": "amount", "label": "AMOUNT"},
                {"key": "average_price", "label": "AVERAGE PRICE"},
            ],
            "rows": rows,
            "empty": len(rows) == 0,
            "empty_message": EMPTY_SALES_MESSAGE if not rows else "",
            "totals": {
                "quantity_sold": quantity_display(total_qty),
                "amount": money_text(total_amount),
                "amount_display": money_display(total_amount),
            },
        }
    )
    return payload


def build_sales_by_sales_person_report(organization, filters):
    country = getattr(organization, "country", None) or "IN"
    date_range = (filters.get("date_range") or "this_month").strip().lower()
    start, end = resolve_date_range(
        date_range,
        filters.get("date_from"),
        filters.get("date_to"),
        country=country,
    )
    invoices = (
        Invoice.objects.filter(
            organization=organization,
            invoice_date__range=(start, end),
        )
        .filter(ACTIVE_INVOICE)
        .prefetch_related("lines")
    )
    grouped = {}
    for invoice in invoices:
        bucket = get_or_create_salesperson_bucket(
            grouped,
            invoice.salesperson_id,
            invoice.salesperson_name,
        )
        line_total = ZERO
        for line in invoice.lines.all():
            line_total += money(line.amount)
        with_tax = money(invoice.total_amount)
        bucket["invoice_count"] += 1
        bucket["invoice_sales"] += line_total if line_total else with_tax
        bucket["invoice_sales_with_tax"] += with_tax

    credit_notes = (
        CreditNote.objects.filter(
            organization=organization,
            credit_note_date__range=(start, end),
        )
        .exclude(status__in=(CreditNote.Status.DRAFT, CreditNote.Status.VOID))
        .select_related("invoice")
    )
    for note in credit_notes:
        invoice = note.invoice
        salesperson_id = invoice.salesperson_id if invoice is not None else None
        salesperson_name = invoice.salesperson_name if invoice is not None else ""
        bucket = get_or_create_salesperson_bucket(
            grouped,
            salesperson_id,
            salesperson_name,
        )
        bucket["credit_note_count"] += 1
        bucket["credit_note_sales"] += money(note.amount)

    rows = []
    totals = {
        "invoice_count": 0,
        "invoice_sales": ZERO,
        "invoice_sales_with_tax": ZERO,
        "credit_note_count": 0,
        "credit_note_sales": ZERO,
    }
    for bucket in sorted(
        grouped.values(),
        key=lambda item: (-item["invoice_sales_with_tax"], item["name"].lower()),
    ):
        totals["invoice_count"] += bucket["invoice_count"]
        totals["invoice_sales"] += bucket["invoice_sales"]
        totals["invoice_sales_with_tax"] += bucket["invoice_sales_with_tax"]
        totals["credit_note_count"] += bucket["credit_note_count"]
        totals["credit_note_sales"] += bucket["credit_note_sales"]
        rows.append(
            {
                "salesperson_id": bucket["salesperson_id"],
                "name": bucket["name"],
                "label": bucket["name"],
                "invoice_count": bucket["invoice_count"],
                "invoice_sales": money_text(bucket["invoice_sales"]),
                "invoice_sales_display": money_display(bucket["invoice_sales"]),
                "invoice_sales_with_tax": money_text(bucket["invoice_sales_with_tax"]),
                "invoice_sales_with_tax_display": money_display(
                    bucket["invoice_sales_with_tax"]
                ),
                "credit_note_count": bucket["credit_note_count"],
                "credit_note_sales": money_text(bucket["credit_note_sales"]),
                "credit_note_sales_display": money_display(bucket["credit_note_sales"]),
            }
        )

    payload = organization_payload(organization)
    payload.update(
        {
            "key": "sales_by_sales_person",
            "title": "Sales by Sales Person",
            "section": "sales",
            "section_label": "Sales",
            "date_range": date_range,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "date_from_display": format_report_date(start),
            "date_to_display": format_report_date(end),
            "period_display": f"From {format_report_date(start)} To {format_report_date(end)}",
            "basis_label": "Basis: Cash",
            "columns": [
                {"key": "name", "label": "NAME"},
                {"key": "invoice_count", "label": "INVOICE COUNT"},
                {"key": "invoice_sales", "label": "INVOICE SALES"},
                {"key": "invoice_sales_with_tax", "label": "INVOICE SALES WITH TAX"},
                {"key": "credit_note_count", "label": "CREDIT NOTE COUNT"},
                {"key": "credit_note_sales", "label": "CREDIT NOTE SALES"},
            ],
            "rows": rows,
            "empty": len(rows) == 0,
            "empty_message": EMPTY_SALES_MESSAGE if not rows else "",
            "totals": {
                "invoice_count": totals["invoice_count"],
                "invoice_sales": money_text(totals["invoice_sales"]),
                "invoice_sales_display": money_display(totals["invoice_sales"]),
                "invoice_sales_with_tax": money_text(totals["invoice_sales_with_tax"]),
                "invoice_sales_with_tax_display": money_display(
                    totals["invoice_sales_with_tax"]
                ),
                "credit_note_count": totals["credit_note_count"],
                "credit_note_sales": money_text(totals["credit_note_sales"]),
                "credit_note_sales_display": money_display(totals["credit_note_sales"]),
            },
        }
    )
    return payload
