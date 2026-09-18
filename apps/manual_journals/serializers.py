import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.organizations.models import Organization
from apps.manual_journals.models import ManualJournal

ZERO = Decimal("0.00")
JOURNAL_NUMBER_RE = re.compile(r"^(?:MJ|JN)-(\d+)$", re.IGNORECASE)

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "AED": "AED",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

ALLOWED_STATUS_TRANSITIONS = {
    ManualJournal.Status.DRAFT: {
        ManualJournal.Status.DRAFT,
        ManualJournal.Status.PUBLISHED,
    },
    ManualJournal.Status.PUBLISHED: {
        ManualJournal.Status.PUBLISHED,
    },
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def currency_symbol(code):
    return CURRENCY_SYMBOLS.get((code or "INR").upper(), code or "INR")


def next_journal_number(organization):
    numbers = ManualJournal.objects.filter(organization=organization).values_list(
        "journal_number",
        flat=True,
    )
    highest = 0
    for number in numbers:
        match = JOURNAL_NUMBER_RE.match((number or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"MJ-{highest + 1:05d}"


class ManualJournalSerializer(serializers.ModelSerializer):
    journal_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    journal_date_label = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    amount_display = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    class Meta:
        model = ManualJournal
        fields = (
            "journal_id",
            "organization_id",
            "journal_number",
            "reference_number",
            "journal_date",
            "journal_date_label",
            "amount",
            "amount_display",
            "currency",
            "currency_symbol",
            "status",
            "status_label",
            "notes",
            "published_at",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_journal_date_label(self, obj):
        if not obj.journal_date:
            return ""
        return obj.journal_date.strftime("%d %b %Y")

    def get_amount(self, obj):
        return money(obj.amount)

    def get_currency_symbol(self, obj):
        return currency_symbol(obj.currency)

    def get_amount_display(self, obj):
        return f"{currency_symbol(obj.currency)}{money(obj.amount)}"


class ManualJournalWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    journal_number = serializers.CharField(required=False, allow_blank=True)
    journal_date = serializers.DateField(required=False, allow_null=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = ManualJournal
        fields = (
            "organization_id",
            "journal_number",
            "reference_number",
            "journal_date",
            "amount",
            "currency",
            "status",
            "notes",
            "action",
        )

    def validate_journal_number(self, value):
        return (value or "").strip().upper()

    def validate_reference_number(self, value):
        return (value or "").strip()

    def validate_status(self, value):
        if not value:
            return ManualJournal.Status.DRAFT
        key = str(value).strip().lower()
        if key not in ManualJournal.Status.values:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(ManualJournal.Status.values)}."
            )
        return key

    def validate_action(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save_as_draft": "save_as_draft",
            "draft": "save_as_draft",
            "save_as_published": "save_as_published",
            "published": "save_as_published",
            "publish": "save_as_published",
            "save": "save_as_published",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save_as_draft, save_as_published."
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
            attrs["status"] = ManualJournal.Status.DRAFT
        elif action == "save_as_published":
            attrs["status"] = ManualJournal.Status.PUBLISHED

        if not attrs.get("journal_date") and not self.partial and not self.instance:
            attrs["journal_date"] = date.today()

        current_status = self.instance.status if self.instance else ManualJournal.Status.DRAFT
        next_status = attrs.get("status", current_status) or ManualJournal.Status.DRAFT
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if next_status not in allowed:
            raise serializers.ValidationError(
                {
                    "status": (
                        f"Cannot change status from {current_status} to {next_status}."
                    )
                }
            )
        return attrs

    def _apply_status_timestamps(self, data, instance=None):
        status_value = data.get("status")
        if status_value == ManualJournal.Status.PUBLISHED and not (
            instance and instance.published_at
        ):
            data["published_at"] = timezone.now()
        return data

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        requested_number = (validated_data.get("journal_number") or "").strip().upper()
        number_taken = (
            bool(requested_number)
            and ManualJournal.objects.filter(
                organization=organization,
                journal_number=requested_number,
            ).exists()
        )
        if not requested_number or number_taken:
            validated_data["journal_number"] = next_journal_number(organization)
        if not validated_data.get("currency"):
            validated_data["currency"] = (
                organization.currency if organization else "INR"
            ) or "INR"
        validated_data = self._apply_status_timestamps(validated_data)
        return ManualJournal.objects.create(
            organization=organization,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        if instance.status == ManualJournal.Status.PUBLISHED and validated_data.get(
            "status", instance.status
        ) == ManualJournal.Status.PUBLISHED:
            locked = {"journal_number", "amount", "journal_date"}
            for field in locked:
                if field in validated_data:
                    validated_data.pop(field)
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        requested_number = validated_data.get("journal_number")
        if requested_number:
            taken = (
                ManualJournal.objects.filter(
                    organization=instance.organization,
                    journal_number=requested_number,
                )
                .exclude(pk=instance.pk)
                .exists()
            )
            if taken:
                validated_data["journal_number"] = next_journal_number(instance.organization)
        validated_data = self._apply_status_timestamps(validated_data, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
