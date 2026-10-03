SECTIONS = (
    ("general", "General"),
    ("customers_vendors", "Customers And Vendors"),
    ("items", "Items"),
    ("quotes", "Quotes"),
    ("invoices", "Invoices"),
    ("credit_notes", "Credit Notes"),
    ("sales_orders", "Sales Orders"),
    ("expenses", "Expenses"),
    ("bills", "Bills"),
    ("purchase_orders", "Purchase Orders"),
    ("vendor_portal", "Vendor Portal"),
)

MODULE_OPTIONS = (
    ("quote", "Quote"),
    ("sales_orders", "Sales Orders"),
    ("delivery_challans", "Delivery Challans"),
    ("purchase_orders", "Purchase Orders"),
    ("time_tracking", "Time Tracking"),
    ("retainer_invoices", "Retainer Invoices"),
    ("recurring_invoice", "Recurring Invoice"),
    ("credit_note", "Credit Note"),
    ("payment_links", "Payment Links"),
)
MODULE_CODES = tuple(code for code, _label in MODULE_OPTIONS)
DEFAULT_ENABLED_MODULES = [
    "quote",
    "sales_orders",
    "delivery_challans",
    "purchase_orders",
    "time_tracking",
    "recurring_invoice",
    "credit_note",
]

DISCOUNT_TYPE_OPTIONS = (
    ("none", "I don't give discounts"),
    ("line_item", "At Line Item Level"),
    ("invoice", "At Invoice Level"),
)

TAX_TYPE_OPTIONS = (
    ("tax_inclusive", "Tax Inclusive"),
    ("tax_exclusive", "Tax Exclusive"),
    ("both", "Tax Inclusive or Tax Exclusive"),
)

ROUNDING_OPTIONS = (
    ("none", "No Rounding"),
    ("nearest_whole", "Round off the total to the nearest whole number"),
)

CUSTOMER_TYPE_OPTIONS = (
    ("business", "Business"),
    ("individual", "Individual"),
)

MILEAGE_UNIT_OPTIONS = (
    ("kilometer", "Kilometer"),
    ("mile", "Mile"),
)

MILEAGE_CATEGORY_OPTIONS = (
    ("fuel_mileage", "Fuel/Mileage Expenses"),
    ("travel", "Travel Expenses"),
    ("vehicle", "Vehicle Expenses"),
)

CUSTOM_FIELD_ENTITIES = (
    ("customers_vendors", "Customers And Vendors"),
    ("items", "Items"),
    ("quotes", "Quotes"),
    ("invoices", "Invoices"),
    ("credit_notes", "Credit Notes"),
    ("sales_orders", "Sales Orders"),
    ("expenses", "Expenses"),
    ("bills", "Bills"),
    ("purchase_orders", "Purchase Orders"),
)

CUSTOM_FIELD_DATA_TYPES = (
    ("text", "Text"),
    ("multiline", "Multi-line Text"),
    ("email", "Email"),
    ("url", "URL"),
    ("phone", "Phone"),
    ("number", "Number"),
    ("decimal", "Decimal"),
    ("amount", "Amount"),
    ("percent", "Percent"),
    ("date", "Date"),
    ("checkbox", "Check Box"),
    ("dropdown", "Dropdown"),
)

ORGANIZATION_PLACEHOLDERS = (
    ("Organization Name", "${ORGANIZATION.NAME}"),
    ("Street Address", "${ORGANIZATION.STREET_ADDRESS}"),
    ("City", "${ORGANIZATION.CITY}"),
    ("State", "${ORGANIZATION.STATE}"),
    ("Postal Code", "${ORGANIZATION.POSTAL_CODE}"),
    ("Country", "${ORGANIZATION.COUNTRY}"),
    ("Phone", "${ORGANIZATION.PHONE}"),
    ("Email", "${ORGANIZATION.EMAIL}"),
    ("Website", "${ORGANIZATION.WEBSITE}"),
    ("TRN", "${ORGANIZATION.TRN_LABEL} ${ORGANIZATION.TRN_VALUE}"),
)

CONTACT_PLACEHOLDERS = (
    ("Display Name", "${CONTACT.CONTACT_DISPLAYNAME}"),
    ("Attention", "${CONTACT.CONTACT_ATTENTION}"),
    ("Address", "${CONTACT.CONTACT_ADDRESS}"),
    ("City", "${CONTACT.CONTACT_CITY}"),
    ("State", "${CONTACT.CONTACT_STATE}"),
    ("Zip Code", "${CONTACT.CONTACT_CODE}"),
    ("Country", "${CONTACT.CONTACT_COUNTRY}"),
    ("Phone", "${CONTACT.CONTACT_PHONE}"),
    ("Fax", "${CONTACT.CONTACT_FAX}"),
    ("TRN", "${CONTACT.TRN_LABEL} ${CONTACT.TRN}"),
)

DEFAULT_ORGANIZATION_ADDRESS_FORMAT = "\n".join(
    [
        "${ORGANIZATION.NAME}",
        "${ORGANIZATION.STREET_ADDRESS}",
        "${ORGANIZATION.CITY} ${ORGANIZATION.STATE}",
        "${ORGANIZATION.POSTAL_CODE}",
        "${ORGANIZATION.COUNTRY}",
        "${ORGANIZATION.TRN_LABEL} ${ORGANIZATION.TRN_VALUE}",
        "${ORGANIZATION.PHONE}",
        "${ORGANIZATION.EMAIL}",
        "${ORGANIZATION.WEBSITE}",
    ]
)

DEFAULT_BILLING_ADDRESS_FORMAT = "\n".join(
    [
        "${CONTACT.CONTACT_DISPLAYNAME}",
        "${CONTACT.CONTACT_ADDRESS}",
        "${CONTACT.CONTACT_CITY}",
        "${CONTACT.CONTACT_CODE} ${CONTACT.CONTACT_STATE}",
        "${CONTACT.CONTACT_COUNTRY}",
        "${CONTACT.TRN_LABEL} ${CONTACT.TRN}",
    ]
)

DEFAULT_SHIPPING_ADDRESS_FORMAT = "\n".join(
    [
        "${CONTACT.CONTACT_ADDRESS}",
        "${CONTACT.CONTACT_CITY}",
        "${CONTACT.CONTACT_CODE} ${CONTACT.CONTACT_STATE}",
        "${CONTACT.CONTACT_COUNTRY}",
        "${CONTACT.TRN_LABEL} ${CONTACT.TRN}",
    ]
)

DEFAULT_QUOTE_NOTES = "Looking forward for your business."
DEFAULT_INVOICE_NOTES = "Thanks for your business."


def options_payload(choices):
    return [{"value": value, "label": label} for value, label in choices]
