from typing import Optional

COUNTRY_CURRENCY_MAP = {
    "IN": "INR",
    "US": "USD",
    "GB": "GBP",
    "AE": "AED",
    "SA": "SAR",
    "CA": "CAD",
    "AU": "AUD",
    "SG": "SGD",
    "MY": "MYR",
    "PK": "PKR",
    "BD": "BDT",
    "LK": "LKR",
    "NP": "NPR",
}

COUNTRY_NAMES = {
    "IN": "India",
    "US": "United States",
    "GB": "United Kingdom",
    "AE": "United Arab Emirates",
    "SA": "Saudi Arabia",
    "CA": "Canada",
    "AU": "Australia",
    "SG": "Singapore",
    "MY": "Malaysia",
    "PK": "Pakistan",
    "BD": "Bangladesh",
    "LK": "Sri Lanka",
    "NP": "Nepal",
}

PHONE_COUNTRY_CODES = {
    "IN": "+91",
    "US": "+1",
    "GB": "+44",
    "AE": "+971",
    "SA": "+966",
    "CA": "+1",
    "AU": "+61",
    "SG": "+65",
    "MY": "+60",
    "PK": "+92",
    "BD": "+880",
    "LK": "+94",
    "NP": "+977",
}

DATA_CENTER_BY_COUNTRY = {
    "IN": "INDIA",
    "US": "UNITED STATES",
    "GB": "UNITED KINGDOM",
    "AE": "UNITED ARAB EMIRATES",
    "SA": "SAUDI ARABIA",
    "CA": "CANADA",
    "AU": "AUSTRALIA",
    "SG": "SINGAPORE",
    "MY": "MALAYSIA",
    "PK": "PAKISTAN",
    "BD": "BANGLADESH",
    "LK": "SRI LANKA",
    "NP": "NEPAL",
}

COUNTRY_STATES = {
    "IN": [
        "Andhra Pradesh",
        "Arunachal Pradesh",
        "Assam",
        "Bihar",
        "Chhattisgarh",
        "Goa",
        "Gujarat",
        "Haryana",
        "Himachal Pradesh",
        "Jharkhand",
        "Karnataka",
        "Kerala",
        "Madhya Pradesh",
        "Maharashtra",
        "Manipur",
        "Meghalaya",
        "Mizoram",
        "Nagaland",
        "Odisha",
        "Punjab",
        "Rajasthan",
        "Sikkim",
        "Tamil Nadu",
        "Telangana",
        "Tripura",
        "Uttar Pradesh",
        "Uttarakhand",
        "West Bengal",
        "Andaman and Nicobar Islands",
        "Chandigarh",
        "Dadra and Nagar Haveli and Daman and Diu",
        "Delhi",
        "Jammu and Kashmir",
        "Ladakh",
        "Lakshadweep",
        "Puducherry",
    ],
}

USER_TYPE_OPTIONS = [
    {"value": "business_user", "label": "Business User"},
    {"value": "tax_consultant", "label": "Tax Consultant"},
    {"value": "student", "label": "Student/Learner"},
]


def is_valid_country(country_code: str) -> bool:
    return country_code.upper() in COUNTRY_CURRENCY_MAP


def get_currency_for_country(country_code: str) -> Optional[str]:
    return COUNTRY_CURRENCY_MAP.get(country_code.upper())


def get_states_for_country(country_code: str) -> list[str]:
    return COUNTRY_STATES.get(country_code.upper(), [])


def get_data_center_for_country(country_code: str) -> str:
    return DATA_CENTER_BY_COUNTRY.get(country_code.upper(), country_code.upper())


def get_countries_list() -> list[dict]:
    return [
        {
            "code": code,
            "name": COUNTRY_NAMES.get(code, code),
            "currency": currency,
            "phone_country_code": PHONE_COUNTRY_CODES.get(code, ""),
            "data_center": get_data_center_for_country(code),
        }
        for code, currency in sorted(COUNTRY_CURRENCY_MAP.items())
    ]


def get_registration_options() -> dict:
    return {
        "user_types": USER_TYPE_OPTIONS,
        "countries": get_countries_list(),
    }
