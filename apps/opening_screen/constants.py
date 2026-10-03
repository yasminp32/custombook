SCREENS = (
    ("home", "Home", "home"),
    ("customers", "Customers", "customers"),
    ("invoices", "Invoices", "invoices"),
    ("items", "Items", "items"),
    ("quotes", "Quotes", "quotes"),
    ("sales_orders", "Sales Orders", "sales_orders"),
    ("vendors", "Vendors", "vendors"),
    ("bills", "Bills", "bills"),
    ("reports", "Reports", "reports"),
    ("settings", "Settings", "settings"),
)

SCREEN_CODES = {code: label for code, label, _icon in SCREENS}
DEFAULT_SCREEN = "home"
