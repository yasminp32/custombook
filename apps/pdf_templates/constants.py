DOCUMENT_TYPES = (
    ("invoices", "Invoices Template", "TAX INVOICE", "INV-17"),
    ("quotes", "Quotes Template", "ESTIMATE", "QT-17"),
    ("sales_orders", "Sales Orders Template", "SALES ORDER", "SO-17"),
    ("purchase_orders", "Purchase Orders Template", "PURCHASE ORDER", "PO-17"),
    ("credit_notes", "Credit Notes Template", "CREDIT NOTE", "CN-17"),
    ("delivery_challans", "Delivery Challans Template", "DELIVERY CHALLAN", "DC-17"),
)

THEMES = (
    ("blue", "Blue", "#2F6BFF"),
    ("green", "Green", "#1F9D55"),
    ("black", "Black", "#1C1C1C"),
    ("red", "Red", "#E23D3D"),
    ("purple", "Purple", "#7A3FF2"),
    ("orange", "Orange", "#F08C2E"),
)

STANDARD_TEMPLATE_NAME = "Standard Template"
DEFAULT_TERMS = (
    "Your company's Terms and Conditions will be displayed here. "
    "You can edit in the more 'settings page under settings'."
)
DEFAULT_NOTES = "Thanks for your business."
SIGNATURE_HINT = "Signature will appear at the bottom of the PDF"

DOCUMENT_TYPE_MAP = {
    code: {"label": label, "title": title, "number": number}
    for code, label, title, number in DOCUMENT_TYPES
}
THEME_MAP = {code: {"label": label, "color": color} for code, label, color in THEMES}


def theme_options():
    return [
        {"value": code, "label": label, "color": color}
        for code, label, color in THEMES
    ]
