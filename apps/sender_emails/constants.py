SYSTEM_FROM_EMAIL = "message.service@sender.techgeum.com"
PRODUCT_EMAIL_LABEL = "Techgeum Email Address"

DELIVERY_METHODS = (
    ("system", PRODUCT_EMAIL_LABEL),
    ("sender", "Sender's Email Address"),
)

PUBLIC_DOMAINS = frozenset(
    {
        "aol.com",
        "gmail.com",
        "gmx.com",
        "googlemail.com",
        "hotmail.com",
        "icloud.com",
        "live.com",
        "mail.com",
        "outlook.com",
        "proton.me",
        "protonmail.com",
        "rediffmail.com",
        "yahoo.com",
        "yahoo.co.in",
        "ymail.com",
        "zoho.com",
    }
)

PUBLIC_DOMAINS_DESCRIPTION = (
    "Emails sent with the following addresses in the From field will be sent from "
    f"{SYSTEM_FROM_EMAIL} to avoid landing in the spam folder."
)

CHOOSE_DELIVERY_DESCRIPTION = "Select how you want to send emails using public domain email addresses."


def email_domain(email):
    address = (email or "").strip().lower()
    if "@" not in address:
        return ""
    return address.rsplit("@", 1)[1]


def is_public_domain(email):
    return email_domain(email) in PUBLIC_DOMAINS
