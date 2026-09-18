from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.organizations.models import Organization
from apps.projects.models import Project
from apps.time_entries.models import TimeEntry

User = get_user_model()

BILLABLE_ALIASES = {
    "true": True,
    "1": True,
    "yes": True,
    "billable": True,
    "false": False,
    "0": False,
    "no": False,
    "non_billable": False,
    "non-billable": False,
    "nonbillable": False,
}


def duration_label(hours, minutes):
    return f"{int(hours or 0)}h {int(minutes or 0)}m"


def user_display_name(user, organization=None):
    if not user:
        return ""
    full_name = (user.get_full_name() or "").strip()
    if organization and user.id == organization.owner_id and organization.name:
        return organization.name
    return full_name or user.email


class TimeEntrySerializer(serializers.ModelSerializer):
    time_entry_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    project_id = serializers.UUIDField(read_only=True, allow_null=True)
    project_name = serializers.SerializerMethodField()
    user_id = serializers.UUIDField(read_only=True, allow_null=True)
    user_name = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    log_date_label = serializers.SerializerMethodField()
    duration_label = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    type_label = serializers.SerializerMethodField()

    class Meta:
        model = TimeEntry
        fields = (
            "time_entry_id",
            "organization_id",
            "project_id",
            "project_name",
            "task_name",
            "user_id",
            "user_name",
            "log_date",
            "log_date_label",
            "hours",
            "minutes",
            "duration_minutes",
            "duration_label",
            "is_billable",
            "type",
            "type_label",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_project_name(self, obj):
        return obj.project.name if obj.project else ""

    def get_user_name(self, obj):
        return user_display_name(obj.user, obj.organization)

    def get_log_date_label(self, obj):
        if not obj.log_date:
            return ""
        return obj.log_date.strftime("%d %b %Y")

    def get_duration_label(self, obj):
        return duration_label(obj.hours, obj.minutes)

    def get_type(self, obj):
        return "billable" if obj.is_billable else "non_billable"

    def get_type_label(self, obj):
        return "BILLABLE" if obj.is_billable else "NON-BILLABLE"


class TimeEntryWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    project_id = serializers.UUIDField(required=False, allow_null=True)
    user_id = serializers.UUIDField(required=False, allow_null=True)
    task_name = serializers.CharField(required=False, allow_blank=True)
    log_date = serializers.DateField(required=False, allow_null=True)
    hours = serializers.IntegerField(required=False)
    minutes = serializers.IntegerField(required=False)
    is_billable = serializers.BooleanField(required=False)
    type = serializers.CharField(required=False, allow_blank=True, write_only=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = TimeEntry
        fields = (
            "organization_id",
            "project_id",
            "user_id",
            "task_name",
            "log_date",
            "hours",
            "minutes",
            "is_billable",
            "type",
            "notes",
        )

    def validate_task_name(self, value):
        return (value or "").strip()

    def validate_notes(self, value):
        return (value or "").strip()

    def validate_hours(self, value):
        hours = 0 if value is None else int(value)
        if hours < 0:
            raise serializers.ValidationError("Hours cannot be negative.")
        return hours

    def validate_minutes(self, value):
        minutes = 0 if value is None else int(value)
        if minutes < 0 or minutes > 59:
            raise serializers.ValidationError("Minutes must be between 0 and 59.")
        return minutes

    def validate_type(self, value):
        if not value:
            return ""
        key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        if key not in BILLABLE_ALIASES:
            raise serializers.ValidationError(
                "Invalid type. Allowed values: billable, non_billable."
            )
        return key

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def validate(self, attrs):
        task_name = attrs.get("task_name")
        if not self.partial and not task_name and not self.instance:
            raise serializers.ValidationError({"task_name": "Task name is required."})

        project_id = attrs.get("project_id")
        if not self.partial and not project_id and not self.instance:
            raise serializers.ValidationError({"project_id": "Project is required."})
        if project_id and not Project.objects.filter(pk=project_id).exists():
            raise serializers.ValidationError({"project_id": "Project not found."})

        user_id = attrs.get("user_id")
        if user_id and not User.objects.filter(pk=user_id).exists():
            raise serializers.ValidationError({"user_id": "User not found."})

        entry_type = attrs.pop("type", "") or ""
        if entry_type:
            attrs["is_billable"] = BILLABLE_ALIASES[entry_type]

        if not attrs.get("log_date") and not self.partial and not self.instance:
            attrs["log_date"] = date.today()
        if "is_billable" not in attrs and not self.instance:
            attrs["is_billable"] = True
        if "hours" not in attrs and not self.instance:
            attrs["hours"] = 0
        if "minutes" not in attrs and not self.instance:
            attrs["minutes"] = 0
        return attrs

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        project_id = validated_data.pop("project_id", None)
        user_id = validated_data.pop("user_id", None)

        project = Project.objects.filter(pk=project_id, organization=organization).first()
        if not project:
            raise serializers.ValidationError({"project_id": "Project not found."})

        user = None
        if user_id:
            user = User.objects.filter(pk=user_id).first()
            if not user:
                raise serializers.ValidationError({"user_id": "User not found."})
        else:
            user = created_by

        return TimeEntry.objects.create(
            organization=organization,
            project=project,
            user=user,
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        project_id = validated_data.pop("project_id", None)
        user_id = validated_data.pop("user_id", None)
        if project_id:
            project = Project.objects.filter(
                pk=project_id,
                organization=instance.organization,
            ).first()
            if not project:
                raise serializers.ValidationError({"project_id": "Project not found."})
            instance.project = project
        if user_id:
            user = User.objects.filter(pk=user_id).first()
            if not user:
                raise serializers.ValidationError({"user_id": "User not found."})
            instance.user = user
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
