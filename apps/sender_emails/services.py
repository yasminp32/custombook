from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.organizations.models import Organization
from apps.organizations.services import get_current_organization
from apps.sender_emails.constants import (
    CHOOSE_DELIVERY_DESCRIPTION,
    DELIVERY_METHODS,
    PRODUCT_EMAIL_LABEL,
    PUBLIC_DOMAINS_DESCRIPTION,
    SYSTEM_FROM_EMAIL,
    email_domain,
    is_public_domain,
)
from apps.sender_emails.models import SenderEmail, SenderEmailPreference

METHOD_LABELS = dict(DELIVERY_METHODS)


def resolve_organization(user, organization_id=None):
    if organization_id:
        return get_object_or_404(Organization.objects.filter(owner=user), pk=organization_id)
    return get_current_organization(user)


def get_preference(organization):
    preference, _created = SenderEmailPreference.objects.get_or_create(organization=organization)
    return preference


def organization_email_choices(organization):
    choices = {}
    owner = organization.owner
    if owner and owner.email:
        choices[owner.email.strip().lower()] = owner.get_full_name().strip() or owner.email
    team_users = organization.team_users.filter(status="active").order_by("full_name", "email")
    for user in team_users:
        if user.email:
            choices[user.email.strip().lower()] = (user.full_name or "").strip() or user.email
    return choices


def available_email_options(organization):
    used = set(SenderEmail.objects.filter(organization=organization).values_list("email", flat=True))
    options = []
    for email, name in organization_email_choices(organization).items():
        if email in used:
            continue
        options.append(
            {
                "email": email,
                "name": name,
                "label": email,
                "domain": email_domain(email),
                "is_public_domain": is_public_domain(email),
            }
        )
    options.sort(key=lambda row: row["email"])
    return options


def primary_contact_email(organization):
    sender = SenderEmail.objects.filter(organization=organization, is_primary=True).first()
    if sender:
        return sender.email
    owner = organization.owner
    if owner and owner.email:
        return owner.email.strip().lower()
    return ""


def sender_payload(sender):
    return {
        "sender_id": str(sender.id),
        "name": sender.name,
        "email": sender.email,
        "is_primary": sender.is_primary,
        "domain": email_domain(sender.email),
        "is_public_domain": is_public_domain(sender.email),
    }


def domain_groups(organization):
    grouped = {}
    senders = SenderEmail.objects.filter(organization=organization)
    for sender in senders:
        domain = email_domain(sender.email) or "unknown"
        grouped.setdefault(domain, []).append(sender_payload(sender))
    groups = []
    for domain, rows in grouped.items():
        public = is_public_domain(f"name@{domain}")
        rows.sort(key=lambda row: (not row["is_primary"], row["name"].lower(), row["email"]))
        groups.append(
            {
                "domain": domain,
                "is_public_domain": public,
                "show_warning": public,
                "senders": rows,
            }
        )
    groups.sort(key=lambda group: (not group["is_public_domain"], group["domain"]))
    return groups


def screen_payload(organization, preference):
    return {
        "title": "Sender Email Preferences",
        "organization_id": str(organization.id),
        "organization_name": organization.name,
        "public_domains": {
            "title": "Public Domains",
            "description": PUBLIC_DOMAINS_DESCRIPTION,
            "system_from_email": SYSTEM_FROM_EMAIL,
            "domains": domain_groups(organization),
        },
        "choose_delivery": {
            "title": "Choose How to Send Emails",
            "description": CHOOSE_DELIVERY_DESCRIPTION,
            "delivery_method": preference.delivery_method,
            "delivery_method_label": METHOD_LABELS.get(preference.delivery_method, ""),
        },
    }


def system_option_description(primary_email):
    reply_target = primary_email or "the primary contact's email address"
    if primary_email:
        reply_target = f"the primary contact's email address, {primary_email}"
    return (
        f"Emails will show {SYSTEM_FROM_EMAIL} in the From field, while replies will go to {reply_target}."
    )


def delivery_payload(organization, preference):
    primary_email = primary_contact_email(organization)
    options = [
        {
            "delivery_method": "system",
            "label": PRODUCT_EMAIL_LABEL,
            "description": system_option_description(primary_email),
            "is_selected": preference.delivery_method == "system",
        },
        {
            "delivery_method": "sender",
            "label": "Sender's Email Address",
            "description": (
                "Emails will show your email address in the From field. To prevent emails "
                "from going to spam, we recommend using the Techgeum email address."
            ),
            "is_selected": preference.delivery_method == "sender",
        },
    ]
    return {
        "title": "Emails Delivery Method",
        "delivery_method": preference.delivery_method,
        "primary_contact_email": primary_email,
        "system_from_email": SYSTEM_FROM_EMAIL,
        "options": options,
    }


def form_payload(organization):
    return {
        "title": "New Sender",
        "name": {"label": "Name", "required": True},
        "email": {
            "label": "Email Address",
            "required": True,
            "placeholder": "Choose sender email address",
            "options": available_email_options(organization),
        },
    }


@transaction.atomic
def create_sender(organization, name, email):
    sender = SenderEmail(
        organization=organization,
        name=name,
        email=email,
        is_primary=not SenderEmail.objects.filter(organization=organization).exists(),
    )
    sender.save()
    return sender


@transaction.atomic
def mark_primary(organization, sender):
    SenderEmail.objects.filter(organization=organization, is_primary=True).exclude(pk=sender.pk).update(
        is_primary=False
    )
    if not sender.is_primary:
        sender.is_primary = True
        sender.save(update_fields=["is_primary", "updated_at"])
    return sender


@transaction.atomic
def delete_sender(organization, sender):
    was_primary = sender.is_primary
    sender.delete()
    if not was_primary:
        return
    replacement = SenderEmail.objects.filter(organization=organization).order_by("created_at").first()
    if replacement and not replacement.is_primary:
        replacement.is_primary = True
        replacement.save(update_fields=["is_primary", "updated_at"])
