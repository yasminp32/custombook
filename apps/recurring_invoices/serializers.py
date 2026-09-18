from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.customers.models import Customer
from apps.organizations.models import Organization
from apps.recurring_invoices.models import RecurringInvoice, RecurringInvoiceActivity

ZERO = Decimal("0.00")

FREQUENCY_ALIASES = {
    "weekly": "weekly",
    "week": "weekly",
    "monthly": "monthly",
    "month": "monthly",
    "quarterly": "quarterly",
    "quarter": "quarterly",
    "yearly": "yearly",
    "year": "yearly",
    "annually": "yearly",
    "annual": "yearly",
}

STATUS_LABELS = {
    RecurringInvoice.Status.DRAFT: "DRAFT",
    RecurringInvoice.Status.ACTIVE: "ACTIVE",
    RecurringInvoice.Status.STOPPED: "STOPPED",
    RecurringInvoice.Status.EXPIRED: "EXPIRED",
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def log_activity(profile, message, user=None, activity_type=RecurringInvoiceActivity.ActivityType.HISTORY):
    RecurringInvoiceActivity.objects.create(
        recurring_invoice=profile,
        activity_type=activity_type,
        message=message,
        created_by=user,
    )


class RecurringInvoiceActivitySerializer(serializers.ModelSerializer):
    activity_id = serializers.UUIDField(source="id", read_only=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RecurringInvoiceActivity
        fields = (
            "activity_id",
            "activity_type",
            "message",
            "created_by",
            "created_by_name",
            "created_at",
        )
        read_only_fields = fields

    def get_created_by_name(self, obj):
        user = obj.created_by
        if not user:
            return ""
        return f"{user.first_name} {user.last_name}".strip() or user.email or ""


class RecurringInvoiceSerializer(serializers.ModelSerializer):
    recurring_invoice_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    stored_status = serializers.CharField(source="status", read_only=True)
    status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    frequency_label = serializers.CharField(source="get_frequency_display", read_only=True)
    start_date_label = serializers.SerializerMethodField()
    end_date_label = serializers.SerializerMethodField()
    next_invoice_date_label = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    comments_and_history = RecurringInvoiceActivitySerializer(
        source="activities",
        many=True,
        read_only=True,
    )

    class Meta:
        model = RecurringInvoice
        fields = (
            "recurring_invoice_id",
            "organization_id",
            "customer_id",
            "customer_name",
            "profile_name",
            "frequency",
            "frequency_label",
            "start_date",
            "start_date_label",
            "end_date",
            "end_date_label",
            "next_invoice_date",
            "next_invoice_date_label",
            "last_invoice_date",
            "amount",
            "currency",
            "stored_status",
            "status",
            "status_label",
            "is_expired",
            "stopped_at",
            "notes",
            "comments_and_history",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_customer_name(self, obj):
        if not obj.customer:
            return ""
        return obj.customer.display_name or obj.customer.company_name or obj.customer.name

    def get_status(self, obj):
        return obj.effective_status()

    def get_status_label(self, obj):
        return STATUS_LABELS.get(obj.effective_status(), obj.effective_status().upper())

    def get_is_expired(self, obj):
        return obj.effective_status() == RecurringInvoice.Status.EXPIRED

    def get_start_date_label(self, obj):
        if not obj.start_date:
            return ""
        return obj.start_date.strftime("%d %b %Y")

    def get_end_date_label(self, obj):
        if not obj.end_date:
            return ""
        return obj.end_date.strftime("%d %b %Y")

    def get_next_invoice_date_label(self, obj):
        if not obj.next_invoice_date:
            return ""
        return obj.next_invoice_date.strftime("%d %b %Y")

    def get_amount(self, obj):
        return money(obj.amount)


class RecurringInvoiceWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    profile_name = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = RecurringInvoice
        fields = (
            "organization_id",
            "customer_id",
            "profile_name",
            "frequency",
            "start_date",
            "end_date",
            "amount",
            "currency",
            "status",
            "notes",
            "action",
        )

    def validate_profile_name(self, value):
        return (value or "").strip()

    def validate_frequency(self, value):
        if not value:
            return RecurringInvoice.Frequency.MONTHLY
        key = str(value).strip().lower().replace(" ", "_")
        mapped = FREQUENCY_ALIASES.get(key)
        if not mapped:
            raise serializers.ValidationError(
                "Invalid frequency. Allowed values: weekly, monthly, quarterly, yearly."
            )
        return mapped

    def validate_status(self, value):
        if not value:
            return RecurringInvoice.Status.ACTIVE
        key = str(value).strip().lower()
        if key not in RecurringInvoice.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(RecurringInvoice.Status.values)}."
            )
        return key

    def validate_action(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save": "save",
            "save_as_active": "save",
            "save_as_draft": "save_as_draft",
            "draft": "save_as_draft",
            "stop": "stop",
            "resume": "resume",
            "activate": "resume",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save, save_as_draft, stop, resume."
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
            attrs["status"] = RecurringInvoice.Status.DRAFT
        elif action == "save":
            attrs["status"] = RecurringInvoice.Status.ACTIVE
        elif action == "stop":
            attrs["status"] = RecurringInvoice.Status.STOPPED
        elif action == "resume":
            attrs["status"] = RecurringInvoice.Status.ACTIVE

        customer_id = attrs.get("customer_id")
        if not self.partial and not customer_id and not self.instance:
            raise serializers.ValidationError({"customer_id": "Customer is required."})
        if customer_id and not Customer.objects.filter(pk=customer_id).exists():
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        profile_name = attrs.get("profile_name")
        if not self.partial and not self.instance and not profile_name:
            raise serializers.ValidationError({"profile_name": "Profile name is required."})

        if not attrs.get("start_date") and not self.partial and not self.instance:
            attrs["start_date"] = date.today()

        amount = attrs.get("amount")
        if not self.partial and not self.instance and (amount is None or Decimal(amount) <= ZERO):
            raise serializers.ValidationError({"amount": "Amount is required."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        customer_id = validated_data.pop("customer_id", None)
        customer = Customer.objects.filter(pk=customer_id, organization=organization).first()
        if not customer:
            raise serializers.ValidationError({"customer_id": "Customer not found."})
        if not validated_data.get("currency"):
            validated_data["currency"] = customer.currency or (
                organization.currency if organization else "INR"
            ) or "INR"
        start_date = validated_data.get("start_date") or date.today()
        validated_data["next_invoice_date"] = start_date
        if (
            validated_data.get("end_date")
            and validated_data["end_date"] < date.today()
            and validated_data.get("status") == RecurringInvoice.Status.ACTIVE
        ):
            validated_data["status"] = RecurringInvoice.Status.EXPIRED
        profile = RecurringInvoice.objects.create(
            organization=organization,
            customer=customer,
            created_by=created_by,
            **validated_data,
        )
        log_activity(
            profile,
            f"Profile created as {profile.get_status_display()}.",
            user=created_by,
        )
        return profile

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        customer_id = validated_data.pop("customer_id", None)
        previous_status = instance.status
        if customer_id:
            customer = Customer.objects.filter(
                pk=customer_id,
                organization=instance.organization,
            ).first()
            if not customer:
                raise serializers.ValidationError({"customer_id": "Customer not found."})
            instance.customer = customer
        next_status = validated_data.get("status", instance.status)
        if next_status == RecurringInvoice.Status.STOPPED and not instance.stopped_at:
            validated_data["stopped_at"] = timezone.now()
        if next_status == RecurringInvoice.Status.ACTIVE:
            validated_data["stopped_at"] = None
            if not instance.next_invoice_date:
                validated_data["next_invoice_date"] = instance.start_date or date.today()
        if "start_date" in validated_data or "frequency" in validated_data:
            start_date = validated_data.get("start_date", instance.start_date)
            frequency = validated_data.get("frequency", instance.frequency)
            instance.frequency = frequency
            instance.start_date = start_date
            if not instance.last_invoice_date:
                validated_data["next_invoice_date"] = start_date
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        user = self.context.get("request").user if self.context.get("request") else None
        if next_status != previous_status:
            log_activity(
                instance,
                f"Status changed from {previous_status} to {next_status}.",
                user=user,
            )
        else:
            log_activity(instance, "Profile updated.", user=user)
        return instance
