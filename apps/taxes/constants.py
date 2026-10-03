REPORTING_PERIODS = (
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("custom", "Custom"),
)

TAX_TYPES = (
    ("tax", "Tax"),
    ("group", "Tax Group"),
)

RATE_ACTIONS = (
    {"code": "group", "label": "New Tax Group"},
    {"code": "tax", "label": "New Tax"},
)

PROFIT_MARGIN_TITLE = "Profit Margin Scheme"
PROFIT_MARGIN_DESCRIPTION = (
    "The Profit Margin Scheme allows you to calculate VAT based on the profit margin "
    "rather than the selling price. This is to avoid double taxation on goods that are "
    "specified in the VAT regulations."
)

INTERNATIONAL_TRADE_NOTE_AE = (
    "Enable this option, if you are doing business with other GCC / Non-GCC countries, "
    "also for reverse charge handling."
)


def options_payload(choices):
    return [{"value": value, "label": label} for value, label in choices]
