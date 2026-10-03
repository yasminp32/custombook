from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.sender_emails.models import SenderEmail
from apps.sender_emails.services import (
    METHOD_LABELS,
    available_email_options,
    create_sender,
    delete_sender,
    delivery_payload,
    domain_groups,
    form_payload,
    get_preference,
    mark_primary,
    organization_email_choices,
    resolve_organization,
    screen_payload,
    sender_payload,
)

NO_ORGANIZATION_MESSAGE = "Organization not found. Complete organization setup first."


def organization_id_from(request):
    return request.query_params.get("organization_id") or request.data.get("organization_id")


def load_organization(request):
    organization = resolve_organization(request.user, organization_id_from(request))
    if not organization:
        return None, api_error(NO_ORGANIZATION_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)
    return organization, None


def sender_id_from(request):
    return (request.query_params.get("sender_id") or request.data.get("sender_id") or "").strip()


def load_sender(organization, request):
    sender_id = sender_id_from(request)
    if not sender_id:
        return None, api_error("sender_id is required.", status_code=status.HTTP_400_BAD_REQUEST)
    sender = get_object_or_404(SenderEmail.objects.filter(organization=organization), pk=sender_id)
    return sender, None


def clean_name(value):
    name = (value or "").strip()
    if not name:
        return None, api_error("Name is required.", status_code=status.HTTP_400_BAD_REQUEST)
    if len(name) > 100:
        return None, api_error("Name cannot be longer than 100 characters.", status_code=status.HTTP_400_BAD_REQUEST)
    return name, None


def clean_email(organization, value, current_email=None):
    email = (value or "").strip().lower()
    if not email:
        return None, api_error("Email Address is required.", status_code=status.HTTP_400_BAD_REQUEST)
    try:
        validate_email(email)
    except ValidationError:
        return None, api_error("Enter a valid email address.", status_code=status.HTTP_400_BAD_REQUEST)
    choices = organization_email_choices(organization)
    if email not in choices:
        return None, api_error(
            "Choose a sender email address from this organization.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if email != (current_email or "") and SenderEmail.objects.filter(organization=organization, email=email).exists():
        return None, api_error("This email address is already a sender.", status_code=status.HTTP_400_BAD_REQUEST)
    return email, None


class SenderEmailIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        preference = get_preference(organization)
        return api_success(data=screen_payload(organization, preference))


class SenderEmailFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        return api_success(data=form_payload(organization))


class SenderEmailListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        sender_id = sender_id_from(request)
        if sender_id:
            sender, sender_error = load_sender(organization, request)
            if sender_error:
                return sender_error
            return api_success(data=sender_payload(sender))
        return api_success(
            data={
                "domains": domain_groups(organization),
                "available_emails": available_email_options(organization),
            }
        )

    def post(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        name, name_error = clean_name(request.data.get("name"))
        if name_error:
            return name_error
        email, email_error = clean_email(organization, request.data.get("email"))
        if email_error:
            return email_error
        try:
            sender = create_sender(organization, name, email)
        except IntegrityError:
            return api_error("This email address is already a sender.", status_code=status.HTTP_400_BAD_REQUEST)
        return api_success(
            data=sender_payload(sender),
            message="Sender saved.",
            status_code=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        sender, sender_error = load_sender(organization, request)
        if sender_error:
            return sender_error
        if "name" in request.data:
            name, name_error = clean_name(request.data.get("name"))
            if name_error:
                return name_error
            sender.name = name
        if "email" in request.data:
            email, email_error = clean_email(organization, request.data.get("email"), current_email=sender.email)
            if email_error:
                return email_error
            sender.email = email
        try:
            sender.save()
        except IntegrityError:
            return api_error("This email address is already a sender.", status_code=status.HTTP_400_BAD_REQUEST)
        return api_success(data=sender_payload(sender), message="Sender updated.")

    def delete(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        sender, sender_error = load_sender(organization, request)
        if sender_error:
            return sender_error
        delete_sender(organization, sender)
        return api_success(
            data={"domains": domain_groups(organization)},
            message="Sender deleted.",
        )


class SenderEmailPrimaryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        sender, sender_error = load_sender(organization, request)
        if sender_error:
            return sender_error
        mark_primary(organization, sender)
        sender.refresh_from_db()
        return api_success(data=sender_payload(sender), message="Primary sender updated.")


class SenderEmailDeliveryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        preference = get_preference(organization)
        return api_success(data=delivery_payload(organization, preference))

    def patch(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        method = (request.data.get("delivery_method") or "").strip()
        if method not in METHOD_LABELS:
            return api_error(
                "Invalid delivery_method. Allowed values: " + ", ".join(METHOD_LABELS) + ".",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        preference = get_preference(organization)
        preference.delivery_method = method
        preference.save(update_fields=["delivery_method", "updated_at"])
        return api_success(data=delivery_payload(organization, preference), message="Email delivery method saved.")
