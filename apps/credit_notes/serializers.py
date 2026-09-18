import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.credit_notes.models import CreditNote
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.organizations.models import Organization

ZERO = Decimal("0.00")
CREDIT_NOTE_NUMBER_RE = re.compile(r"^CN-(\d+)$", re.IGNORECASE)

ALLOWED_STATUS_TRANSITIONS = {
    CreditNote.Status.DRAFT: {
        CreditNote.Status.DRAFT,
        CreditNote.Status.OPEN,
        CreditNote.Status.VOID,
    },
    CreditNote.Status.OPEN: {
        CreditNote.Status.OPEN,
        CreditNote.Status.CLOSED,
        CreditNote.Status.VOID,
    },
    CreditNote.Status.CLOSED: {
        CreditNote.Status.CLOSED,
    },
    CreditNote.Status.VOID: {
        CreditNote.Status.VOID,
    },
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def next_credit_note_number(organization):
    numbers = CreditNote.objects.filter(organization=organization).values_list(
        "credit_note_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = CREDIT_NOTE_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"CN-{highest + 1:05d}"


class CreditNoteSerializer(serializers.ModelSerializer):
    credit_note_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_name = serializers.SerializerMethodField()
    invoice_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    credit_note_date_label = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = CreditNote
        fields = (
            "credit_note_id",
            "organization_id",
            "customer_id",
            "customer_name",
            "invoice_id",
            "credit_note_number",
            "reference_number",
            "credit_note_date",
            "credit_note_date_label",
            "amount",
            "currency",
            "status",
            "status_label",
            "notes",
            "closed_at",
            "voided_at",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_customer_name(self, obj):
        if not obj.customer:
            return ""
        return obj.customer.display_name or obj.customer.company_name or obj.customer.name

    def get_credit_note_date_label(self, obj):
        if not obj.credit_note_date:
            return ""
        return obj.credit_note_date.strftime("%d %b %Y")

    def get_amount(self, obj):
        return money(obj.amount)


class CreditNoteWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    invoice_id = serializers.UUIDField(required=False, allow_null=True)
    credit_note_number = serializers.CharField(required=False, allow_blank=True)
    credit_note_date = serializers.DateField(required=False, allow_null=True)
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = CreditNote
        fields = (
            "organization_id",
            "customer_id",
            "invoice_id",
            "credit_note_number",
            "reference_number",
            "credit_note_date",
            "amount",
            "currency",
            "status",
            "notes",
            "action",
        )

    def validate_credit_note_number(self, value):
        return (value or "").strip().upper()

    def validate_status(self, value):
        if not value:
            return CreditNote.Status.DRAFT
        key = str(value).strip().lower()
        if key not in CreditNote.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(CreditNote.Status.values)}."
            )
        return key

    def validate_action(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save_as_draft": "save_as_draft",
            "draft": "save_as_draft",
            "save_as_open": "save_as_open",
            "open": "save_as_open",
            "save": "save_as_open",
            "close": "close",
            "void": "void",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save_as_draft, save_as_open, close, void."
            )
        return aliases[key]

    def validate_amount(self, value):
        if value is None:
            return ZERO
        amount = Decimal(value)
        if amount < ZERO:
            raise serializers.ValidationError("Amount cannot be negative.")
        return amount

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        action = attrs.pop("action", "") or ""
        if action == "save_as_draft":
            attrs["status"] = CreditNote.Status.DRAFT
        elif action == "save_as_open":
            attrs["status"] = CreditNote.Status.OPEN
        elif action == "close":
            attrs["status"] = CreditNote.Status.CLOSED
        elif action == "void":
            attrs["status"] = CreditNote.Status.VOID

        customer_id = attrs.get("customer_id")
        if not self.partial and not customer_id and not self.instance:
            raise serializers.ValidationError({"customer_id": "Customer is required."})
        if customer_id and not Customer.objects.filter(pk=customer_id).exists():
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        invoice_id = attrs.get("invoice_id")
        if invoice_id and not Invoice.objects.filter(pk=invoice_id).exists():
            raise serializers.ValidationError({"invoice_id": "Invoice not found."})

        if not attrs.get("credit_note_date") and not self.partial and not self.instance:
            attrs["credit_note_date"] = date.today()

        current_status = self.instance.status if self.instance else CreditNote.Status.DRAFT
        next_status = attrs.get("status", current_status) or CreditNote.Status.DRAFT
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if next_status not in allowed:
            raise serializers.ValidationError(
                {
                    "status": (
                        f"Cannot change status from {current_status} to {next_status}."
                    )
                }
            )

        amount = attrs.get("amount")
        if amount is None and self.instance:
            amount = self.instance.amount
        if next_status == CreditNote.Status.OPEN and (amount is None or Decimal(amount) <= ZERO):
            raise serializers.ValidationError(
                {"amount": "Amount is required before saving as open."}
            )
        return attrs

    def _apply_status_timestamps(self, data, instance=None):
        status_value = data.get("status")
        if status_value == CreditNote.Status.CLOSED and not (instance and instance.closed_at):
            data["closed_at"] = timezone.now()
        if status_value == CreditNote.Status.VOID and not (instance and instance.voided_at):
            data["voided_at"] = timezone.now()
        return data

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        customer_id = validated_data.pop("customer_id", None)
        invoice_id = validated_data.pop("invoice_id", None)
        customer = Customer.objects.filter(pk=customer_id, organization=organization).first()
        if not customer:
            raise serializers.ValidationError({"customer_id": "Customer not found."})
        invoice = None
        if invoice_id:
            invoice = Invoice.objects.filter(
                pk=invoice_id,
                organization=organization,
            ).first()
            if not invoice:
                raise serializers.ValidationError({"invoice_id": "Invoice not found."})
        requested_number = (validated_data.get("credit_note_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and CreditNote.objects.filter(
                organization=organization,
                credit_note_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["credit_note_number"] = next_credit_note_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = customer.currency or (
                organization.currency if organization else "INR"
            ) or "INR"
        validated_data = self._apply_status_timestamps(validated_data)
        return CreditNote.objects.create(
            organization=organization,
            customer=customer,
            invoice=invoice,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        if instance.status in (CreditNote.Status.CLOSED, CreditNote.Status.VOID):
            raise serializers.ValidationError(
                {"status": "Closed or void credit notes cannot be updated."}
            )
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        customer_id = validated_data.pop("customer_id", None)
        invoice_id = validated_data.pop("invoice_id", None)
        if customer_id:
            customer = Customer.objects.filter(
                pk=customer_id,
                organization=instance.organization,
            ).first()
            if not customer:
                raise serializers.ValidationError({"customer_id": "Customer not found."})
            instance.customer = customer
        if invoice_id:
            invoice = Invoice.objects.filter(
                pk=invoice_id,
                organization=instance.organization,
            ).first()
            if not invoice:
                raise serializers.ValidationError({"invoice_id": "Invoice not found."})
            instance.invoice = invoice
        validated_data = self._apply_status_timestamps(validated_data, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
