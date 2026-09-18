import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.organizations.models import Organization
from apps.payments_received.models import PaymentReceived, PaymentReceivedApplication

ZERO = Decimal("0.00")
PAYMENT_NUMBER_RE = re.compile(r"^PR-(\d+)$", re.IGNORECASE)

PAYMENT_MODE_ALIASES = {
    "cash": "cash",
    "bank_transfer": "bank_transfer",
    "bank transfer": "bank_transfer",
    "banktransfer": "bank_transfer",
    "card": "card",
    "cheque": "cheque",
    "check": "cheque",
    "upi": "upi",
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def next_payment_number(organization):
    numbers = PaymentReceived.objects.filter(organization=organization).values_list(
        "payment_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = PAYMENT_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"PR-{highest + 1:05d}"


def invoice_balance(invoice):
    total = Decimal(invoice.total_amount or 0)
    paid = Decimal(invoice.amount_paid or 0)
    remaining = total - paid
    return remaining if remaining > ZERO else ZERO


def refresh_invoice_from_payments(invoice):
    paid = Decimal(invoice.amount_paid or 0)
    total = Decimal(invoice.total_amount or 0)
    if paid <= ZERO:
        if invoice.status in (Invoice.Status.PAID, Invoice.Status.PARTIALLY_PAID):
            invoice.status = Invoice.Status.SENT
            invoice.payment_received = False
            invoice.paid_at = None
    elif paid >= total and total > ZERO:
        invoice.status = Invoice.Status.PAID
        invoice.payment_received = True
        if not invoice.paid_at:
            invoice.paid_at = timezone.now()
    else:
        invoice.status = Invoice.Status.PARTIALLY_PAID
        invoice.payment_received = False
        invoice.paid_at = None
    invoice.save(
        update_fields=["amount_paid", "status", "payment_received", "paid_at", "updated_at"]
    )


def apply_amount_to_invoice(payment, invoice, amount):
    if invoice.customer_id != payment.customer_id:
        raise serializers.ValidationError(
            {"invoice_id": "Invoice does not belong to this customer."}
        )
    if invoice.organization_id != payment.organization_id:
        raise serializers.ValidationError({"invoice_id": "Invoice not found."})
    if invoice.status == Invoice.Status.CANCELLED:
        raise serializers.ValidationError({"invoice_id": "Cancelled invoices cannot receive payments."})

    apply_amount = Decimal(amount or 0)
    if apply_amount <= ZERO:
        raise serializers.ValidationError({"amount": "Application amount must be greater than zero."})

    unused = payment.unused_amount
    balance = invoice_balance(invoice)
    if apply_amount > unused:
        apply_amount = unused
    if apply_amount > balance:
        apply_amount = balance
    if apply_amount <= ZERO:
        raise serializers.ValidationError(
            {"amount": "No unused payment or invoice balance remaining."}
        )

    application, created = PaymentReceivedApplication.objects.get_or_create(
        payment=payment,
        invoice=invoice,
        defaults={"amount": apply_amount},
    )
    if not created:
        application.amount = Decimal(application.amount or 0) + apply_amount
        application.save(update_fields=["amount"])

    payment.amount_applied = Decimal(payment.amount_applied or 0) + apply_amount
    payment.save(update_fields=["amount_applied", "updated_at"])

    invoice.amount_paid = Decimal(invoice.amount_paid or 0) + apply_amount
    refresh_invoice_from_payments(invoice)
    return application, apply_amount


def reverse_application(application):
    payment = application.payment
    invoice = application.invoice
    amount = Decimal(application.amount or 0)
    application.delete()
    payment.amount_applied = max(Decimal(payment.amount_applied or 0) - amount, ZERO)
    payment.save(update_fields=["amount_applied", "updated_at"])
    invoice.amount_paid = max(Decimal(invoice.amount_paid or 0) - amount, ZERO)
    refresh_invoice_from_payments(invoice)


class PaymentApplicationSerializer(serializers.ModelSerializer):
    application_id = serializers.UUIDField(source="id", read_only=True)
    invoice_id = serializers.UUIDField(read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = PaymentReceivedApplication
        fields = ("application_id", "invoice_id", "invoice_number", "amount")
        read_only_fields = fields

    def get_amount(self, obj):
        return money(obj.amount)


class PaymentApplicationWriteSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )


class PaymentReceivedSerializer(serializers.ModelSerializer):
    payment_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    payment_mode_label = serializers.CharField(source="get_payment_mode_display", read_only=True)
    payment_date_label = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    amount_applied = serializers.SerializerMethodField()
    unused_amount = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    is_unapplied = serializers.SerializerMethodField()
    applications = PaymentApplicationSerializer(many=True, read_only=True)

    class Meta:
        model = PaymentReceived
        fields = (
            "payment_id",
            "organization_id",
            "customer_id",
            "customer_name",
            "payment_number",
            "payment_date",
            "payment_date_label",
            "payment_mode",
            "payment_mode_label",
            "reference_number",
            "amount",
            "amount_applied",
            "unused_amount",
            "currency",
            "status",
            "status_label",
            "is_unapplied",
            "notes",
            "bank_account_id",
            "applications",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_customer_name(self, obj):
        if not obj.customer:
            return ""
        return obj.customer.display_name or obj.customer.company_name or obj.customer.name

    def get_payment_date_label(self, obj):
        if not obj.payment_date:
            return ""
        return obj.payment_date.strftime("%d %b %Y")

    def get_amount(self, obj):
        return money(obj.amount)

    def get_amount_applied(self, obj):
        return money(obj.amount_applied)

    def get_unused_amount(self, obj):
        return money(obj.unused_amount)

    def get_status(self, obj):
        return obj.application_status()

    def get_status_label(self, obj):
        return "Unapplied" if obj.is_unapplied() else "Applied"

    def get_is_unapplied(self, obj):
        return obj.is_unapplied()


class PaymentReceivedWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    invoice_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    payment_number = serializers.CharField(required=False, allow_blank=True)
    payment_date = serializers.DateField(required=False, allow_null=True)
    applications = PaymentApplicationWriteSerializer(many=True, required=False)

    class Meta:
        model = PaymentReceived
        fields = (
            "organization_id",
            "customer_id",
            "invoice_id",
            "payment_number",
            "payment_date",
            "payment_mode",
            "reference_number",
            "amount",
            "currency",
            "notes",
            "bank_account_id",
            "applications",
        )

    def validate_payment_number(self, value):
        return (value or "").strip().upper()

    def validate_payment_mode(self, value):
        if not value:
            return PaymentReceived.PaymentMode.BANK_TRANSFER
        key = str(value).strip().lower()
        mapped = PAYMENT_MODE_ALIASES.get(key) or PAYMENT_MODE_ALIASES.get(key.replace(" ", "_"))
        if not mapped:
            raise serializers.ValidationError(
                "Invalid payment mode. Allowed values: cash, bank_transfer, card, cheque, upi."
            )
        return mapped

    def validate_amount(self, value):
        amount = Decimal(value or 0)
        if amount <= ZERO:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return amount

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        customer_id = attrs.get("customer_id")
        if not self.partial and not customer_id and not self.instance:
            raise serializers.ValidationError({"customer_id": "Customer is required."})
        if customer_id and not Customer.objects.filter(pk=customer_id).exists():
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        if not attrs.get("payment_date") and not self.partial and not self.instance:
            attrs["payment_date"] = date.today()

        invoice_id = attrs.get("invoice_id")
        if invoice_id and not Invoice.objects.filter(pk=invoice_id).exists():
            raise serializers.ValidationError({"invoice_id": "Invoice not found."})
        return attrs

    def _apply_targets(self, payment, invoice_id, applications):
        targets = list(applications or [])
        if invoice_id and not targets:
            targets = [{"invoice_id": invoice_id, "amount": payment.unused_amount}]
        for row in targets:
            invoice = Invoice.objects.filter(
                pk=row["invoice_id"],
                organization=payment.organization,
            ).first()
            if not invoice:
                raise serializers.ValidationError({"invoice_id": "Invoice not found."})
            amount = row.get("amount")
            if amount is None:
                amount = min(payment.unused_amount, invoice_balance(invoice))
            apply_amount_to_invoice(payment, invoice, amount)

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        customer_id = validated_data.pop("customer_id", None)
        invoice_id = validated_data.pop("invoice_id", None)
        applications = validated_data.pop("applications", None)

        customer = Customer.objects.filter(pk=customer_id, organization=organization).first()
        if not customer:
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        requested_number = (validated_data.get("payment_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and PaymentReceived.objects.filter(
                organization=organization,
                payment_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["payment_number"] = next_payment_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = customer.currency or (
                organization.currency if organization else "INR"
            ) or "INR"

        payment = PaymentReceived.objects.create(
            organization=organization,
            customer=customer,
            created_by=created_by,
            **validated_data,
        )
        self._apply_targets(payment, invoice_id, applications)
        payment.refresh_from_db()
        return payment

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        customer_id = validated_data.pop("customer_id", None)
        invoice_id = validated_data.pop("invoice_id", None)
        applications = validated_data.pop("applications", None)
        if customer_id:
            if instance.applications.exists():
                raise serializers.ValidationError(
                    {"customer_id": "Customer cannot be changed after the payment is applied."}
                )
            customer = Customer.objects.filter(
                pk=customer_id,
                organization=instance.organization,
            ).first()
            if not customer:
                raise serializers.ValidationError({"customer_id": "Customer not found."})
            instance.customer = customer
        new_amount = validated_data.get("amount")
        if new_amount is not None and Decimal(new_amount) < Decimal(instance.amount_applied or 0):
            raise serializers.ValidationError(
                {"amount": "Amount cannot be less than the applied amount."}
            )
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if invoice_id or applications:
            self._apply_targets(instance, invoice_id, applications)
        instance.refresh_from_db()
        return instance
