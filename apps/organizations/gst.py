import re

from django.core.exceptions import ValidationError

# GST state codes (first 2 digits of GSTIN) mapped to state names
GSTIN_STATE_CODE_MAP = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}

GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)


def get_state_from_gstin(gstin: str):
    if not gstin or len(gstin) < 2:
        return None
    return GSTIN_STATE_CODE_MAP.get(gstin[:2].upper())


def validate_gstin(gstin: str) -> str:
    normalized = gstin.strip().upper()
    if not GSTIN_PATTERN.match(normalized):
        raise ValidationError("Invalid GSTIN format.")
    state = get_state_from_gstin(normalized)
    if not state:
        raise ValidationError("Invalid GSTIN state code.")
    return normalized
