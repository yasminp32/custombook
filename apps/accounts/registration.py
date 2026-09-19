from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.countries import get_currency_for_country, get_data_center_for_country
from apps.accounts.models import User
from apps.accounts.services import create_and_send_otp
from apps.organizations.models import Organization


@transaction.atomic
def register_user_with_organization(validated_data):
    company_name = validated_data.pop("company_name", "")
    country = validated_data.pop("country")
    state = validated_data.pop("state", "")
    terms_accepted = validated_data.pop("terms_accepted")

    skip_email_otp = settings.SKIP_EMAIL_OTP
    user = User.objects.create_user(
        **validated_data,
        terms_accepted_at=timezone.now() if terms_accepted else None,
        is_email_verified=skip_email_otp,
    )

    organization = None
    if company_name:
        organization = Organization.objects.create(
            name=company_name,
            country=country,
            state=state,
            currency=get_currency_for_country(country) or "INR",
            owner=user,
        )

    payload = {
        "user": user,
        "organization": organization,
        "data_center": get_data_center_for_country(country),
        "email_sent": False,
        "skip_email_otp": skip_email_otp,
    }
    if skip_email_otp:
        return payload

    otp = create_and_send_otp(user)
    payload["email_sent"] = getattr(otp, "email_sent", True)
    if settings.DEBUG and not payload["email_sent"]:
        payload["otp_code"] = otp.code
    return payload
