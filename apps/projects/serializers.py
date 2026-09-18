from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import serializers

from apps.customers.models import Customer
from apps.organizations.models import Organization
from apps.projects.models import ZERO, Project

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "AED": "AED",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

BILLING_METHOD_ALIASES = {
    "fixed_cost": Project.BillingMethod.FIXED_COST,
    "fixed cost": Project.BillingMethod.FIXED_COST,
    "fixed_cost_for_project": Project.BillingMethod.FIXED_COST,
    "fixed cost for project": Project.BillingMethod.FIXED_COST,
    "project_hours": Project.BillingMethod.PROJECT_HOURS,
    "based_on_project_hours": Project.BillingMethod.PROJECT_HOURS,
    "based on project hours": Project.BillingMethod.PROJECT_HOURS,
    "staff_hours": Project.BillingMethod.STAFF_HOURS,
    "based_on_staff_hours": Project.BillingMethod.STAFF_HOURS,
    "based on staff hours": Project.BillingMethod.STAFF_HOURS,
    "task_hours": Project.BillingMethod.TASK_HOURS,
    "based_on_task_hours": Project.BillingMethod.TASK_HOURS,
    "based on task hours": Project.BillingMethod.TASK_HOURS,
}

STATUS_ALIASES = {
    "active": Project.Status.ACTIVE,
    "on_hold": Project.Status.ON_HOLD,
    "on hold": Project.Status.ON_HOLD,
    "hold": Project.Status.ON_HOLD,
    "completed": Project.Status.COMPLETED,
    "cancelled": Project.Status.CANCELLED,
    "canceled": Project.Status.CANCELLED,
}

ALLOWED_STATUS_TRANSITIONS = {
    Project.Status.ACTIVE: {
        Project.Status.ACTIVE,
        Project.Status.ON_HOLD,
        Project.Status.COMPLETED,
        Project.Status.CANCELLED,
    },
    Project.Status.ON_HOLD: {
        Project.Status.ON_HOLD,
        Project.Status.ACTIVE,
        Project.Status.CANCELLED,
    },
    Project.Status.COMPLETED: {
        Project.Status.COMPLETED,
    },
    Project.Status.CANCELLED: {
        Project.Status.CANCELLED,
    },
}


def money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def hours_value(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount == amount.to_integral_value():
        return str(int(amount))
    return f"{amount:.2f}"


def currency_symbol(code):
    return CURRENCY_SYMBOLS.get((code or "INR").upper(), code or "INR")


class ProjectSerializer(serializers.ModelSerializer):
    project_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    billing_method_label = serializers.CharField(
        source="get_billing_method_display",
        read_only=True,
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    rate = serializers.SerializerMethodField()
    budget_hours = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "project_id",
            "organization_id",
            "customer_id",
            "customer_name",
            "name",
            "billing_method",
            "billing_method_label",
            "rate",
            "budget_hours",
            "amount",
            "currency",
            "currency_symbol",
            "status",
            "status_label",
            "notes",
            "completed_at",
            "cancelled_at",
            "on_hold_at",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_customer_name(self, obj):
        if not obj.customer:
            return ""
        return obj.customer.display_name or obj.customer.company_name or obj.customer.name

    def get_rate(self, obj):
        return money(obj.rate)

    def get_budget_hours(self, obj):
        return hours_value(obj.budget_hours)

    def get_amount(self, obj):
        return money(obj.computed_amount())

    def get_currency_symbol(self, obj):
        return currency_symbol(obj.currency)


class ProjectWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True)
    action = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Project
        fields = (
            "organization_id",
            "customer_id",
            "name",
            "billing_method",
            "rate",
            "budget_hours",
            "currency",
            "status",
            "notes",
            "action",
        )

    def validate_name(self, value):
        return (value or "").strip()

    def validate_billing_method(self, value):
        if not value:
            return Project.BillingMethod.FIXED_COST
        key = str(value).strip().lower()
        mapped = BILLING_METHOD_ALIASES.get(key) or BILLING_METHOD_ALIASES.get(
            key.replace(" ", "_")
        )
        if not mapped:
            raise serializers.ValidationError(
                "Invalid billing method. Allowed values: fixed_cost, project_hours, "
                "staff_hours, task_hours."
            )
        return mapped

    def validate_status(self, value):
        if not value:
            return Project.Status.ACTIVE
        key = str(value).strip().lower()
        mapped = STATUS_ALIASES.get(key) or STATUS_ALIASES.get(key.replace(" ", "_"))
        if not mapped:
            raise serializers.ValidationError(
                "Invalid status. Allowed values: active, on_hold, completed, cancelled."
            )
        return mapped

    def validate_action(self, value):
        if not value:
            return "save"
        key = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "save": "save",
            "mark_completed": "mark_completed",
            "complete": "mark_completed",
            "mark_on_hold": "mark_on_hold",
            "on_hold": "mark_on_hold",
            "hold": "mark_on_hold",
            "cancel": "cancel",
            "mark_active": "mark_active",
            "activate": "mark_active",
        }
        if key not in aliases:
            raise serializers.ValidationError(
                "Invalid action. Allowed values: save, mark_completed, mark_on_hold, "
                "cancel, mark_active."
            )
        return aliases[key]

    def validate_rate(self, value):
        amount = Decimal(value or 0)
        if amount < ZERO:
            raise serializers.ValidationError("Rate cannot be negative.")
        return amount

    def validate_budget_hours(self, value):
        hours = Decimal(value or 0)
        if hours < ZERO:
            raise serializers.ValidationError("Budget hours cannot be negative.")
        return hours

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        action = attrs.pop("action", "") or "save"
        if action == "save" and not self.instance:
            attrs["status"] = Project.Status.ACTIVE
        elif action == "mark_completed":
            attrs["status"] = Project.Status.COMPLETED
        elif action == "mark_on_hold":
            attrs["status"] = Project.Status.ON_HOLD
        elif action == "cancel":
            attrs["status"] = Project.Status.CANCELLED
        elif action == "mark_active":
            attrs["status"] = Project.Status.ACTIVE

        name = attrs.get("name")
        if not self.partial and not name and not self.instance:
            raise serializers.ValidationError({"name": "Project name is required."})

        customer_id = attrs.get("customer_id")
        if not self.partial and not customer_id and not self.instance:
            raise serializers.ValidationError({"customer_id": "Customer is required."})
        if customer_id and not Customer.objects.filter(pk=customer_id).exists():
            raise serializers.ValidationError({"customer_id": "Customer not found."})

        current_status = self.instance.status if self.instance else Project.Status.ACTIVE
        next_status = attrs.get("status", current_status) or Project.Status.ACTIVE
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
        if status_value == Project.Status.COMPLETED and not (
            instance and instance.completed_at
        ):
            data["completed_at"] = timezone.now()
        if status_value == Project.Status.CANCELLED and not (
            instance and instance.cancelled_at
        ):
            data["cancelled_at"] = timezone.now()
        if status_value == Project.Status.ON_HOLD and not (instance and instance.on_hold_at):
            data["on_hold_at"] = timezone.now()
        return data

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        customer_id = validated_data.pop("customer_id", None)
        customer = Customer.objects.filter(pk=customer_id, organization=organization).first()
        if not customer:
            raise serializers.ValidationError({"customer_id": "Customer not found."})
        if not validated_data.get("billing_method"):
            validated_data["billing_method"] = Project.BillingMethod.FIXED_COST
        if not validated_data.get("currency"):
            validated_data["currency"] = customer.currency or (
                organization.currency if organization else "INR"
            ) or "INR"
        validated_data = self._apply_status_timestamps(validated_data)
        return Project.objects.create(
            organization=organization,
            customer=customer,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        if instance.status in (Project.Status.COMPLETED, Project.Status.CANCELLED):
            raise serializers.ValidationError(
                {"status": "Completed or cancelled projects cannot be updated."}
            )
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        customer_id = validated_data.pop("customer_id", None)
        if customer_id:
            customer = Customer.objects.filter(
                pk=customer_id,
                organization=instance.organization,
            ).first()
            if not customer:
                raise serializers.ValidationError({"customer_id": "Customer not found."})
            instance.customer = customer
        validated_data = self._apply_status_timestamps(validated_data, instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
