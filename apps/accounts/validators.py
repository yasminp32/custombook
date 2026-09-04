import re

from django.core.exceptions import ValidationError

from apps.accounts.countries import PHONE_COUNTRY_CODES, get_states_for_country, is_valid_country


def validate_password_strength(password):
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one digit.")


def validate_phone_country_code(value):
    normalized = value.strip()
    if not normalized.startswith("+"):
        raise ValidationError("Phone country code must start with '+'.")
    if normalized not in PHONE_COUNTRY_CODES.values():
        raise ValidationError("Unsupported phone country code.")
    return normalized


def validate_phone_number(value):
    digits = re.sub(r"\D", "", value)
    if len(digits) < 6 or len(digits) > 15:
        raise ValidationError("Phone number must be between 6 and 15 digits.")
    return digits


def validate_country_code(value):
    code = value.upper()
    if not is_valid_country(code):
        raise ValidationError("Unsupported country.")
    return code


def validate_state_for_country(country_code, state):
    states = get_states_for_country(country_code)
    if not states:
        return state.strip()

    if not state:
        raise ValidationError("State is required for the selected country.")

    if state not in states:
        raise ValidationError("Invalid state for the selected country.")

    return state
