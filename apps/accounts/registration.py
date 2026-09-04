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

    user = User.objects.create_user(
        **validated_data,
        terms_accepted_at=timezone.now() if terms_accepted else None,
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

    create_and_send_otp(user)

    return {
        "user": user,
        "organization": organization,
        "data_center": get_data_center_for_country(country),
    }
