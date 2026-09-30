import re
from email.utils import formataddr

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email

from apps.customers.models import CustomerContactPerson
from apps.payments_received.pdf import build_receipt_pdf, receipt_filename
from apps.payments_received.services import (
    currency_amount,
    customer_display_name,
    display_name_for_user,
)

MAX_RECIPIENTS = 20
SPLIT_RE = re.compile(r"[,;\s]+")


def default_subject(payment):
    organization_name = payment.organization.name if payment.organization else ""
    subject = f"Payment Receipt - {payment.payment_number}"
    if organization_name:
        subject += f" from {organization_name}"
    return subject


def default_body(payment, user):
    organization = payment.organization
    invoice_numbers = ", ".join(
        row.invoice.invoice_number for row in payment.applications.select_related("invoice")
    )
    lines = [
        f"Dear {customer_display_name(payment.customer) or 'Customer'},",
        "",
        "Thank you for your payment. It was a pleasure doing business with you. "
        "We look forward to work together again!",
        "",
        "-" * 60,
        f"Payment Received: {currency_amount(payment.currency, payment.amount)}",
        f"Payment Date: {payment.payment_date.strftime('%d %b %Y') if payment.payment_date else ''}",
        f"Payment Mode: {payment.get_payment_mode_display()}",
    ]
    if payment.reference_number:
        lines.append(f"Reference Number: {payment.reference_number}")
    if invoice_numbers:
        lines.append(f"Invoice Number(s): {invoice_numbers}")
    lines += [
        "-" * 60,
        "",
        "Regards,",
        display_name_for_user(user, organization),
    ]
    if organization and organization.name:
        lines.append(organization.name)
    return "\n".join(lines)


def recipient_options(payment):
    customer = payment.customer
    if not customer:
        return []
    options = []
    seen = set()
    if customer.email:
        options.append(
            {
                "name": customer_display_name(customer),
                "email": customer.email,
                "type": "customer",
            }
        )
        seen.add(customer.email.lower())
    for person in CustomerContactPerson.objects.filter(customer=customer).exclude(email=""):
        if person.email.lower() in seen:
            continue
        seen.add(person.email.lower())
        name = " ".join(
            part for part in (person.salutation, person.first_name, person.last_name) if part
        )
        options.append({"name": name or person.email, "email": person.email, "type": "contact_person"})
    return options


def build_email_form(payment, user):
    options = recipient_options(payment)
    return {
        "title": f"Email To {customer_display_name(payment.customer)}".strip(),
        "from": {
            "name": display_name_for_user(user, payment.organization),
            "email": user.email,
        },
        "to": [options[0]["email"]] if options else [],
        "to_options": options,
        "cc": [],
        "bcc": [],
        "subject": default_subject(payment),
        "body": default_body(payment, user),
        "attach_pdf": True,
        "attachment": {
            "file_name": receipt_filename(payment),
            "download_path": f"/api/payments-received/pdf/?payment_id={payment.id}",
        },
        "send_path": f"/api/payments-received/email/?payment_id={payment.id}",
    }


def parse_recipients(value, field_name, errors, required=False):
    if value is None or value == "":
        values = []
    elif isinstance(value, (list, tuple)):
        values = [str(item).strip() for item in value if str(item).strip()]
    else:
        values = [item for item in SPLIT_RE.split(str(value)) if item]
    cleaned = []
    for email in values:
        try:
            validate_email(email)
        except ValidationError:
            errors[field_name] = f"Invalid email address: {email}"
            return []
        if email.lower() not in (item.lower() for item in cleaned):
            cleaned.append(email)
    if required and not cleaned:
        errors[field_name] = "At least one recipient is required."
    elif len(cleaned) > MAX_RECIPIENTS:
        errors[field_name] = f"A maximum of {MAX_RECIPIENTS} recipients is allowed."
    return cleaned


def send_receipt_email(payment, user, to, cc, bcc, subject, body, attach_pdf):
    organization_name = payment.organization.name if payment.organization else ""
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=formataddr((organization_name, settings.DEFAULT_FROM_EMAIL))
        if organization_name
        else settings.DEFAULT_FROM_EMAIL,
        to=to,
        cc=cc,
        bcc=bcc,
        reply_to=[user.email] if user.email else None,
    )
    if attach_pdf:
        message.attach(receipt_filename(payment), build_receipt_pdf(payment), "application/pdf")
    message.send(fail_silently=False)
