REPORT_CATALOG = (
    {
        "section": "financial_reports",
        "section_label": "Financial Reports",
        "reports": (
            ("balance_sheet", "Balance Sheet"),
            ("profit_and_loss", "Profit and Loss"),
            ("cash_flow_statement", "Cash Flow Statement"),
        ),
    },
    {
        "section": "sales",
        "section_label": "Sales",
        "reports": (
            ("sales_by_customer", "Sales by Customer"),
            ("sales_by_item", "Sales by Item"),
            ("sales_by_sales_person", "Sales by Sales Person"),
        ),
    },
    {
        "section": "receivables",
        "section_label": "Receivables",
        "reports": (
            ("customer_balance_summary", "Customer Balance Summary"),
            ("ar_aging_summary", "AR Aging Summary"),
            ("ar_aging_details", "AR Aging Details"),
            ("payments_received", "Payments Received"),
        ),
    },
    {
        "section": "expenses",
        "section_label": "Expenses",
        "reports": (
            ("expenses_by_category", "Expenses by Category"),
        ),
    },
    {
        "section": "payables",
        "section_label": "Payables",
        "reports": (
            ("payments_made", "Payments Made"),
            ("vendor_balance_summary", "Vendor Balance Summary"),
        ),
    },
)


FINANCIAL_PATHS = {
    "balance_sheet": "/api/reports/financial/balance-sheet/",
    "profit_and_loss": "/api/reports/financial/profit-and-loss/",
    "cash_flow_statement": "/api/reports/financial/cash-flow-statement/",
}


SALES_PATHS = {
    "sales_by_customer": "/api/reports/sales/sales-by-customer/",
    "sales_by_item": "/api/reports/sales/sales-by-item/",
    "sales_by_sales_person": "/api/reports/sales/sales-by-sales-person/",
}


RECEIVABLE_PATHS = {
    "customer_balance_summary": "/api/reports/receivables/customer-balance-summary/",
    "ar_aging_summary": "/api/reports/receivables/ar-aging-summary/",
    "ar_aging_details": "/api/reports/receivables/ar-aging-details/",
    "payments_received": "/api/reports/receivables/payments-received/",
}


EXPENSE_PATHS = {
    "expenses_by_category": "/api/reports/expenses/expenses-by-category/",
}


PAYABLE_PATHS = {
    "payments_made": "/api/reports/payables/payments-made/",
    "vendor_balance_summary": "/api/reports/payables/vendor-balance-summary/",
}


def report_path(key):
    if key in FINANCIAL_PATHS:
        return FINANCIAL_PATHS[key]
    if key in SALES_PATHS:
        return SALES_PATHS[key]
    if key in RECEIVABLE_PATHS:
        return RECEIVABLE_PATHS[key]
    if key in EXPENSE_PATHS:
        return EXPENSE_PATHS[key]
    if key in PAYABLE_PATHS:
        return PAYABLE_PATHS[key]
    return f"/api/reports/?report_key={key}"


def all_reports():
    items = []
    for section in REPORT_CATALOG:
        for key, label in section["reports"]:
            items.append(
                {
                    "key": key,
                    "label": label,
                    "section": section["section"],
                    "section_label": section["section_label"],
                    "path": report_path(key),
                }
            )
    return items


def catalog_payload(search=""):
    query = (search or "").strip().lower()
    groups = []
    for section in REPORT_CATALOG:
        reports = []
        for key, label in section["reports"]:
            if query and query not in key and query not in label.lower():
                continue
            reports.append(
                {
                    "key": key,
                    "label": label,
                    "path": report_path(key),
                }
            )
        if reports:
            groups.append(
                {
                    "section": section["section"],
                    "section_label": section["section_label"],
                    "reports": reports,
                }
            )
    return {
        "title": "Reports",
        "groups": groups,
        "reports": all_reports() if not query else [
            row for group in groups for row in [
                {
                    "key": item["key"],
                    "label": item["label"],
                    "section": group["section"],
                    "section_label": group["section_label"],
                    "path": item["path"],
                }
                for item in group["reports"]
            ]
        ],
    }


def get_report_meta(report_key):
    key = (report_key or "").strip().lower()
    for item in all_reports():
        if item["key"] == key:
            return item
    return None
