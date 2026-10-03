from decimal import Decimal, ROUND_HALF_UP

# code: (name, symbol, default decimal places)
CURRENCY_CATALOG = {
    "AED": ("UAE Dirham", "AED", 2),
    "AUD": ("Australian Dollar", "$", 2),
    "BND": ("Brunei Dollar", "$", 2),
    "CAD": ("Canadian Dollar", "$", 2),
    "CHF": ("Swiss Franc", "CHF", 2),
    "CNY": ("Yuan Renminbi", "¥", 2),
    "EUR": ("Euro", "€", 2),
    "GBP": ("Pound Sterling", "£", 2),
    "HKD": ("Hong Kong Dollar", "$", 2),
    "INR": ("Indian Rupee", "₹", 2),
    "JPY": ("Japanese Yen", "¥", 0),
    "KRW": ("Won", "₩", 0),
    "MYR": ("Malaysian Ringgit", "RM", 2),
    "NZD": ("New Zealand Dollar", "$", 2),
    "PHP": ("Philippine Peso", "₱", 2),
    "SAR": ("Saudi Riyal", "SAR", 2),
    "SGD": ("Singapore Dollar", "$", 2),
    "THB": ("Baht", "฿", 2),
    "USD": ("United States Dollar", "$", 2),
    "ZAR": ("South African Rand", "R", 2),
    # Codes used by organization setup that are not in the picker list
    "PKR": ("Pakistan Rupee", "Rs", 2),
    "BDT": ("Taka", "৳", 2),
    "LKR": ("Sri Lanka Rupee", "Rs", 2),
    "NPR": ("Nepalese Rupee", "Rs", 2),
}

# Currency codes offered in the "Select Currency Code" sheet
CURRENCY_CODE_OPTIONS = [
    "AED", "AUD", "BND", "CAD", "CHF", "CNY", "EUR", "GBP", "HKD", "INR",
    "JPY", "KRW", "MYR", "NZD", "PHP", "SAR", "SGD", "THB", "USD", "ZAR",
]

# Currencies created automatically for a new organization (base currency is always added first)
DEFAULT_CURRENCIES = ["AED", "AUD", "BND", "CAD", "CNY", "EUR", "GBP", "JPY", "SAR", "USD", "ZAR"]

DECIMAL_PLACES_OPTIONS = (0, 2, 3)

FORMAT_OPTIONS = (
    ("comma_dot", "1,234,567.89"),
    ("dot_comma", "1.234.567,89"),
    ("space_dot", "1 234 567.89"),
)

FTA_NOTICE = {
    "message": (
        "Caution: According to FTA rules, you're required to use the exchange rates "
        "recommended by the Central Bank Of UAE for VAT-transactions."
    ),
    "link_text": "Central Bank Of Uae",
    "link_url": "https://www.centralbank.ae/en/forex-eibor/exchange-rates/",
}


def format_amount(value, decimal_places=2, number_format="comma_dot"):
    quantum = Decimal(1).scaleb(-int(decimal_places)) if decimal_places else Decimal(1)
    amount = Decimal(value or 0).quantize(quantum, rounding=ROUND_HALF_UP)
    negative = amount < 0
    amount = abs(amount)
    whole, _, fraction = f"{amount:f}".partition(".")
    if number_format == "dot_comma":
        group_sep, decimal_sep = ".", ","
    elif number_format == "space_dot":
        group_sep, decimal_sep = " ", "."
    else:
        group_sep, decimal_sep = ",", "."
    grouped = f"{int(whole):,}".replace(",", group_sep)
    text = f"{grouped}{decimal_sep}{fraction}" if decimal_places else grouped
    return f"-{text}" if negative else text
