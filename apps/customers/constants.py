CUSTOMER_TYPES = (
    ("business", "Business"),
    ("individual", "Individual"),
)

SALUTATIONS = (
    ("mr", "Mr."),
    ("mrs", "Mrs."),
    ("ms", "Ms."),
    ("miss", "Miss."),
    ("dr", "Dr."),
)

SALUTATION_ALIASES = {
    "mr": "mr",
    "mr.": "mr",
    "mrs": "mrs",
    "mrs.": "mrs",
    "ms": "ms",
    "ms.": "ms",
    "miss": "miss",
    "miss.": "miss",
    "dr": "dr",
    "dr.": "dr",
}

TAX_TREATMENTS = (
    ("gst_registered", "GST Registered"),
    ("non_gst_registered", "Non GST Registered"),
    ("gst_registered_composition", "GST Registered - Composition"),
    ("consumer", "Consumer"),
    ("overseas", "Overseas"),
    ("sez", "SEZ"),
)

TAX_TREATMENT_ALIASES = {
    "gst registered": "gst_registered",
    "gst_registered": "gst_registered",
    "non gst registered": "non_gst_registered",
    "non_gst_registered": "non_gst_registered",
    "gst registered - composition": "gst_registered_composition",
    "gst_registered_composition": "gst_registered_composition",
    "consumer": "consumer",
    "overseas": "overseas",
    "sez": "sez",
}

PAYMENT_TERMS = (
    ("due_on_receipt", "Due on Receipt"),
    ("net_15", "Net 15"),
    ("net_30", "Net 30"),
    ("net_45", "Net 45"),
    ("net_60", "Net 60"),
    ("due_end_of_month", "Due end of the month"),
    ("due_end_of_next_month", "Due end of next month"),
)

PAYMENT_TERM_ALIASES = {
    "due on receipt": "due_on_receipt",
    "due_on_receipt": "due_on_receipt",
    "net 15": "net_15",
    "net_15": "net_15",
    "net 30": "net_30",
    "net_30": "net_30",
    "net 45": "net_45",
    "net_45": "net_45",
    "net 60": "net_60",
    "net_60": "net_60",
    "due end of the month": "due_end_of_month",
    "due_end_of_month": "due_end_of_month",
    "due end of next month": "due_end_of_next_month",
    "due_end_of_next_month": "due_end_of_next_month",
}

ACCOUNTS_RECEIVABLE = (
    ("accounts_receivable", "Accounts Receivable"),
    ("accounts_receivable_domestic", "Accounts Receivable - Domestic"),
    ("accounts_receivable_foreign", "Accounts Receivable - Foreign"),
)

ACCOUNTS_RECEIVABLE_ALIASES = {
    "accounts receivable": "accounts_receivable",
    "accounts_receivable": "accounts_receivable",
    "accounts receivable - domestic": "accounts_receivable_domestic",
    "accounts_receivable_domestic": "accounts_receivable_domestic",
    "accounts receivable - foreign": "accounts_receivable_foreign",
    "accounts_receivable_foreign": "accounts_receivable_foreign",
}

PORTAL_LANGUAGES = (
    ("en", "English"),
    ("hi", "Hindi"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("mr", "Marathi"),
    ("bn", "Bengali"),
    ("gu", "Gujarati"),
)

PORTAL_LANGUAGE_ALIASES = {
    "en": "en",
    "english": "en",
    "hi": "hi",
    "hindi": "hi",
    "ta": "ta",
    "tamil": "ta",
    "te": "te",
    "telugu": "te",
    "mr": "mr",
    "marathi": "mr",
    "bn": "bn",
    "bengali": "bn",
    "gu": "gu",
    "gujarati": "gu",
}

CUSTOMER_CURRENCIES = (
    ("INR", "INR - Indian Rupee"),
    ("USD", "USD - United States Dollar"),
    ("EUR", "EUR - Euro"),
    ("GBP", "GBP - Pound Sterling"),
    ("AED", "AED - UAE Dirham"),
    ("CAD", "CAD - Canadian Dollar"),
    ("AUD", "AUD - Australian Dollar"),
    ("SGD", "SGD - Singapore Dollar"),
    ("JPY", "JPY - Japanese Yen"),
    ("CNY", "CNY - Yuan Renminbi"),
)

SOCIAL_PLATFORMS = (
    ("website", "Website"),
    ("facebook", "Facebook"),
    ("twitter", "Twitter"),
    ("linkedin", "LinkedIn"),
    ("instagram", "Instagram"),
    ("youtube", "YouTube"),
    ("other", "Other"),
)


def choice_options(choices):
    return [{"key": key, "label": label} for key, label in choices]


def normalize_choice(value, aliases, allowed):
    if value is None:
        return ""
    key = str(value).strip()
    if not key:
        return ""
    normalized = aliases.get(key.lower(), aliases.get(key, key.lower()))
    if normalized not in allowed:
        labels = ", ".join(allowed)
        raise ValueError(f"Invalid value. Allowed values: {labels}.")
    return normalized
