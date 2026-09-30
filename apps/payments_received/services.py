from decimal import Decimal, ROUND_HALF_UP

from apps.banking.models import BankAccount
from apps.payments_received.models import PaymentReceived, PaymentReceivedActivity

ATTACHABLE_TYPE = "payment_received"


def log_activity(
    payment,
    message,
    user=None,
    activity_type=PaymentReceivedActivity.ActivityType.HISTORY,
):
    return PaymentReceivedActivity.objects.create(
        payment=payment,
        activity_type=activity_type,
        message=message,
        created_by=user,
    )


def display_name_for_user(user, organization=None):
    if user:
        full_name = (user.get_full_name() or "").strip()
        if full_name:
            return full_name
        if user.email:
            return user.email
    if organization and organization.name:
        return organization.name
    return ""


def currency_amount(currency, value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{currency or ''}{amount:,.2f}"


def customer_display_name(customer):
    if not customer:
        return ""
    return customer.display_name or customer.company_name or customer.name


def deposit_account(payment):
    if not payment.bank_account_id:
        return None
    return BankAccount.objects.filter(
        pk=payment.bank_account_id,
        organization_id=payment.organization_id,
    ).first()


def template_options(selected=None):
    return [
        {"key": key, "label": label, "is_selected": key == selected}
        for key, label in PaymentReceived.Template.choices
    ]


def applications_snapshot(payment):
    return {
        str(row.invoice_id): Decimal(row.amount or 0)
        for row in payment.applications.all()
    }


def edit_snapshot(payment):
    return {
        "payment_number": payment.payment_number,
        "payment_date": payment.payment_date,
        "payment_mode": payment.payment_mode,
        "reference_number": payment.reference_number,
        "amount": Decimal(payment.amount or 0),
        "bank_charges": Decimal(payment.bank_charges or 0),
        "currency": payment.currency,
        "notes": payment.notes,
        "bank_account_id": payment.bank_account_id,
        "customer_id": payment.customer_id,
    }
