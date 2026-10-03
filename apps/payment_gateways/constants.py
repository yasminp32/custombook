PAYMENT_METHODS = (
    ("credit_debit_card", "CREDIT/DEBIT CARD"),
    ("ideal", "IDEAL"),
    ("giropay", "GIROPAY"),
    ("bancontact", "BANCONTACT"),
    ("sofort", "SOFORT"),
    ("alipay", "ALIPAY"),
    ("klarna", "KLARNA"),
    ("paynow", "PAYNOW"),
    ("grabpay", "GRABPAY"),
    ("others", "OTHERS"),
)

GATEWAYS = (
    {
        "code": "stripe",
        "name": "Stripe",
        "is_preferred": True,
        "description": (
            "Stripe is an online payment processing platform that allows you to receive "
            "one-time and recurring payments securely from customers."
        ),
    },
    {
        "code": "paytabs",
        "name": "PayTabs",
        "is_preferred": False,
        "description": (
            "PayTabs is a simple payment gateway that will allow you to accept payments "
            "in nearly 168 currencies from your customers across the globe. This is ideal "
            "for businesses that sell globally."
        ),
    },
    {
        "code": "two_checkout",
        "name": "2Checkout (Verifone)",
        "is_preferred": False,
        "description": (
            "2Checkout enables businesses to accept mobile and online payments from buyers "
            "worldwide. It is ideal for businesses that sell products internationally."
        ),
    },
    {
        "code": "braintree",
        "name": "Braintree",
        "is_preferred": False,
        "description": (
            "Braintree Payments is an all-in-one solution to accept and process payments "
            "in your mobile and on the web. Set up Braintree to accept payments in multiple "
            "currencies from over 45+ countries."
        ),
    },
)

METHOD_GATEWAYS = {
    "credit_debit_card": ("stripe", "paytabs", "two_checkout", "braintree"),
    "ideal": ("stripe",),
    "giropay": ("stripe",),
    "bancontact": ("stripe",),
    "sofort": ("stripe",),
    "alipay": ("stripe",),
    "klarna": ("stripe",),
    "paynow": ("stripe",),
    "grabpay": ("stripe",),
    "others": ("stripe",),
}

GATEWAY_MAP = {gateway["code"]: gateway for gateway in GATEWAYS}
METHOD_MAP = {code: label for code, label in PAYMENT_METHODS}
